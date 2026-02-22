# -*- coding: utf-8 -*-
"""
modules/bind/watch_media.py — svyazka Watch→Media: skaniruem direktorii po maskam, dedupim i progonyaem novye fayly cherez /media/video/ingest.

Mosty:
- Yavnyy: (Watch ↔ Media) avtomatiziruet put «nashel — razobral — v pamyat».
- Skrytyy #1: (Profile ↔ Prozrachnost) kazhdyy progon i kazhdoe prinyatie fayla fiksiruetsya.
- Skrytyy #2: (RAG/KG ↔ Navigatsiya) downstream uzhe delaet rag_append i autolink v ingest.

Zemnoy abzats:
Eto kak konveyer na sklade: kamera uvidela korobku — lenta sama povezla ee na sortirovku, a kladovschik vse otmetil v zhurnale.

# c=a+b
"""
from __future__ import annotations
import os, json, time, fnmatch, hashlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB  = os.getenv("BIND_WATCH_DB","data/bind/watch_media.json")
DEF = [p.strip() for p in (os.getenv("BIND_DEFAULT_PATTERNS","*.mp4,*.mkv,*.webm,*.avi,*.mov,*.m4v,*.mp3,*.wav") or "").split(",") if p.strip()]
os.makedirs(os.path.dirname(DB), exist_ok=True)

def _load():
    if not os.path.isfile(DB):
        json.dump({"roots": [], "patterns": DEF, "seen": {}, "stats": {"scans":0, "ingested":0}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return json.load(open(DB,"r",encoding="utf-8"))

def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _fingerprint(path: str)->str:
    try:
        st=os.stat(path)
        sz=str(st.st_size); mt=str(int(st.st_mtime))
        h=hashlib.sha256()
        with open(path,"rb") as f:
            chunk=f.read(262144)  # 256 KiB
            h.update(chunk or b"")
        h.update(sz.encode()); h.update(mt.encode())
        return h.hexdigest()
    except Exception:
        return hashlib.sha256(path.encode()).hexdigest()

def config(roots: list[str]|None=None, patterns: list[str]|None=None)->dict:
    j=_load()
    if roots is not None: j["roots"]=[os.path.abspath(r) for r in roots if r]
    if patterns is not None: j["patterns"]=[p for p in patterns if p]
    _save(j)
    _passport("bind_watch_config", {"roots": len(j["roots"]), "patterns": len(j["patterns"])})
    return {"ok": True, "roots": j["roots"], "patterns": j["patterns"]}

def status()->dict:
    j=_load()
    st=j.get("stats") or {}
    return {"ok": True, "roots": j.get("roots") or [], "patterns": j.get("patterns") or [], "stats": st, "seen_count": len(j.get("seen") or {})}

def _call_ingest(path: str)->dict:
    import urllib.request, json as _j
    data=_j.dumps({"path": path, "prefer_subs": True, "transcribe": False}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000/media/video/ingest", data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=21600) as r:
            return _j.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run(override_roots: list[str]|None=None, override_patterns: list[str]|None=None)->dict:
    j=_load()
    roots    = [os.path.abspath(r) for r in (override_roots if override_roots is not None else j.get("roots") or [])]
    patterns = (override_patterns if override_patterns is not None else j.get("patterns") or DEF)
    if not roots: 
        return {"ok": True, "scanned": 0, "ingested": 0, "note": "no_roots_configured"}
    seen=j.get("seen") or {}
    scanned=0; ing=0; accepted=[]
    for root in roots:
        for base,_,names in os.walk(root):
            for n in names:
                if not any(fnmatch.fnmatch(n, p) for p in patterns): 
                    continue
                p=os.path.abspath(os.path.join(base,n))
                scanned+=1
                fp=_fingerprint(p)
                if seen.get(fp):
                    continue
                rep=_call_ingest(p)
                if rep.get("ok"):
                    seen[fp]={"path": p, "t": int(time.time())}
                    ing+=1; accepted.append({"path": p, "id": rep.get("id")})
    j["seen"]=seen; S=j.get("stats") or {}; S["scans"]=int(S.get("scans",0))+1; S["ingested"]=int(S.get("ingested",0))+ing; j["stats"]=S; _save(j)
    _passport("bind_watch_run", {"roots": len(roots), "scanned": scanned, "ingested": ing})
    return {"ok": True, "scanned": scanned, "ingested": ing, "accepted": accepted}

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "bind://watch_media")
    except Exception:
        pass
# c=a+b