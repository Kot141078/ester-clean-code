# -*- coding: utf-8 -*-
"""modules/watch/folder_scanner.py - oflayn-scanner papok: new/izmenennye fayly → kontekst pravil.

Mosty:
- Yavnyy: (FS ↔ Volya) nakhodit izmenennye fayly i formiruet context dlya pravil.
- Skrytyy #1: (Profile ↔ Prozrachnost) logiruem fakty obnaruzheniya/obrabotki.
- Skrytyy #2: (RAG/Media ↔ Integratsiya) cherez pravila vyzyvayutsya ingest/pamyat/poisk.

Zemnoy abzats:
Eto "pochtovyy yaschik": nakidyvaesh tuda fayly - scanner otmechaet novoe i zapuskaet nuzhnye deystviya.

# c=a+b"""
from __future__ import annotations
import os, json, time, hashlib, fnmatch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("WATCH_DB","data/watch/index.json")
DIRS=[d.strip() for d in (os.getenv("WATCH_DIRS","data/inbox") or "").split(",") if d.strip()]
PATS=[p.strip() for p in (os.getenv("WATCH_PATTERNS","*.mp4,*.mkv,*.mp3,*.wav,*.srt,*.vtt,*.txt,*.pdf") or "").split(",") if p.strip()]
AUTOPROC=(os.getenv("WATCH_AUTOPROCESS","true").lower()=="true")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"files":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    for d in DIRS: os.makedirs(d, exist_ok=True)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _sha256_file(path: str, size_limit: int=20_000_000)->str:
    h=hashlib.sha256()
    try:
        with open(path,"rb") as f:
            # read up to 20MB for a fast hash (enough for video)
            left=size_limit
            while left>0:
                chunk=f.read(min(8192, left))
                if not chunk: break
                h.update(chunk); left-=len(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "watch://scanner")
    except Exception:
        pass

def scan(autoprocess: bool|None=None)->dict:
    j=_load(); files=j.get("files") or {}
    autoprocess = AUTOPROC if autoprocess is None else bool(autoprocess)
    new=[]; changed=[]
    for d in DIRS:
        for root,_,names in os.walk(d):
            for n in names:
                if not any(fnmatch.fnmatch(n, p) for p in PATS): 
                    continue
                path=os.path.join(root,n)
                try:
                    st=os.stat(path)
                except Exception:
                    continue
                key=os.path.abspath(path)
                ext=os.path.splitext(n)[1].lower()
                rec=files.get(key)
                sh=_sha256_file(path)
                if not rec:
                    files[key]={"sha": sh, "mtime": int(st.st_mtime), "ext": ext, "size": int(st.st_size)}
                    new.append({"path": key, "ext": ext, "size": int(st.st_size), "basename": n})
                else:
                    if rec.get("sha")!=sh or rec.get("mtime")!=int(st.st_mtime):
                        rec.update({"sha": sh, "mtime": int(st.st_mtime), "size": int(st.st_size)})
                        changed.append({"path": key, "ext": ext, "size": int(st.st_size), "basename": n})
    j["files"]=files; _save(j)
    _passport("watch_scan", {"new": len(new), "changed": len(changed)})

    report={"ok": True, "new": new, "changed": changed}
    if autoprocess and (new or changed):
        try:
            from modules.thinking.rules_engine import evaluate  # type: ignore
            hits=[]
            for item in new:
                ctx={"when":"on_watch_new","path": item["path"], "ext": item["ext"], "size": item["size"], "basename": item["basename"]}
                rep=evaluate(ctx); hits.append(rep)
            report["auto"]=hits
        except Exception:
            report["auto_error"]=True
    return report

def status()->dict:
    j=_load()
    return {"ok": True, "dirs": DIRS, "patterns": PATS, "count": len(j.get("files") or {}), "autoprocess": AUTOPROC}

def set_config(dirs: list[str]|None, patterns: list[str]|None)->dict:
    global DIRS, PATS
    if dirs: DIRS=[d.strip() for d in dirs if d and d.strip()]
    if patterns: PATS=[p.strip() for p in patterns if p and p.strip()]
    # peresozdadim papki
    for d in DIRS: 
        try: os.makedirs(d, exist_ok=True)
        except Exception: pass
    _passport("watch_config_set", {"dirs": len(DIRS), "patterns": len(PATS)})
    return {"ok": True, "dirs": DIRS, "patterns": PATS}
# c=a+b