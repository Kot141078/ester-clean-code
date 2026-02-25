# -*- coding: utf-8 -*-
"""modules/media/video_ingest.py - oflayn/onlayn-inzhest video: ffprobe → subtitry/ASR → chernovoy konspekt.

Mosty:
- Yavnyy: (Video ↔ Memory/Poisk) metadannye + tekst v pamyat i gibridnyy poisk.
- Skrytyy #1: (Legalnost/Kvoty ↔ Ostorozhnost) legal_check + ingest_quota pered setevymi shagami.
- Skrytyy #2: (KG ↔ Navigatsiya) avtolink suschnostey iz konspekta/subtitrov.

Zemnoy abzats:
Kak “magnitofon s bloknotom”: snyali tekhdannye, vytaschili rech/subtitry, nakidali chernovye tezisy - i polozhili na polku.

# c=a+b"""
from __future__ import annotations
import os, re, json, time, hashlib, subprocess, tempfile, shutil
from typing import Any, Dict, Tuple, List
from modules.media.utils import passport, rag_append, kg_autolink, legal_check, ingest_quota
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEDIA_DB=os.getenv("MEDIA_DB","data/media/index.json")
MEDIA_DIR=os.getenv("MEDIA_DIR","data/media")
FFPROBE=os.getenv("MEDIA_FFPROBE","ffprobe")
YTDLP=os.getenv("MEDIA_YTDLP","yt-dlp")
WHISPER=os.getenv("MEDIA_WHISPER","whisper")
WHISPER_ARGS=os.getenv("MEDIA_WHISPER_ARGS","--language auto --task transcribe")
ALLOW_NET=(os.getenv("MEDIA_ALLOW_NETWORK","true").lower()=="true")

def _ensure():
    os.makedirs(MEDIA_DIR, exist_ok=True)
    if not os.path.isfile(MEDIA_DB):
        json.dump({"items":[]}, open(MEDIA_DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(MEDIA_DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(MEDIA_DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _id_of(s: str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def _run(cmd: List[str], timeout: int=180)->Tuple[int,str,str]:
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        return p.returncode, p.stdout.decode("utf-8","ignore"), p.stderr.decode("utf-8","ignore")
    except Exception as e:
        return 127, "", str(e)

def _ffprobe(path: str)->Dict[str,Any]:
    if not shutil.which(FFPROBE):
        return {"ok": False, "error":"ffprobe_missing"}
    code,out,err=_run([FFPROBE,"-v","error","-print_format","json","-show_format","-show_streams",path], 60)
    if code==0:
        try: return {"ok": True, "meta": json.loads(out)}
        except Exception: return {"ok": False, "error":"ffprobe_parse"}
    return {"ok": False, "error": err[:200]}

def _ytdlp_info(url: str, outdir: str)->Dict[str,Any]:
    if not (ALLOW_NET and shutil.which(YTDLP)):
        return {"ok": False, "error":"ytdlp_unavailable"}
    code,out,err=_run([YTDLP,"-J",url], 120)
    meta={}
    if code==0:
        try: meta=json.loads(out)
        except Exception: pass
    # subtitles (best-effort: only uploading .vtt, if available)
    subs_text=""
    try:
        _run([YTDLP,"--skip-download","--write-auto-subs","--sub-format","vtt","-o",os.path.join(outdir,"%(id)s.%(ext)s"), url], 300)
        # ischem vtt
        for n in os.listdir(outdir):
            if n.lower().endswith(".vtt"):
                subs_text=open(os.path.join(outdir,n),"r",encoding="utf-8",errors="ignore").read()
                break
    except Exception:
        pass
    return {"ok": True, "meta": meta, "subs": subs_text}

def _whisper_transcribe(path: str)->str:
    if not shutil.which(WHISPER):
        return ""
    args=[WHISPER] + WHISPER_ARGS.split() + [path]
    code,out,err=_run(args, 900)
    # many KLIS keep .txt nearby; let's try to catch the output
    txt=""
    # simple hit: take the last 32K stdout as text
    if out.strip():
        txt=out[-32000:]
    # if .txt appears nearby, we’ll read it
    base=os.path.splitext(path)[0]
    for cand in (base+".txt", base+".vtt", base+".srt"):
        if os.path.isfile(cand):
            try: txt=open(cand,"r",encoding="utf-8",errors="ignore").read()
            except Exception: pass
    return txt

def _notes_from_text(text: str, max_bullets: int=12)->str:
    # prostaya “kondensatsiya”: razbivka na stroki/frazy, chastotnye slova → top-frazy
    import re, math
    s=re.sub(r"\s+"," ", text or ""); s=s.strip()
    if not s: return ""
    sents=re.split(r"(?<=[\.\!\?])\s+", s)
    tokens=[w.lower() for w in re.findall(r"[A-Za-zA-Yaa-yaEe0-9']+", s) if len(w)>2]
    if not tokens: return ""
    freq={}
    for w in tokens: freq[w]=freq.get(w,0)+1
    scores=[]
    for i,sen in enumerate(sents):
        ws=[w.lower() for w in re.findall(r"[A-Za-zA-Yaa-yaEe0-9']+", sen)]
        sc=sum(freq.get(w,0) for w in ws) / max(1,len(ws))
        scores.append((sc, i, sen))
    scores.sort(reverse=True)
    top=[x[2] for x in scores[:max_bullets]]
    bullets="\n".join(f"- {t}" for t in top)
    return bullets

def ingest(url: str|None=None, path: str|None=None, prefer_subs: bool=True, transcribe: bool=False, language: str="auto")->Dict[str,Any]:
    _ensure()
    source=url or path or ""
    if not source: return {"ok": False, "error":"no_source"}
    service=("local" if path else re.sub(r"^https?://(www\\.)?","", url or "").split("/")[0])
    # Legalnost/kvota
    lg=legal_check("media_ingest", service)
    if lg.get("verdict")=="deny": 
        return {"ok": False, "error":"legal_denied", "service": service}
    qt=ingest_quota(service or "media", 10)
    if not qt.get("allowed"): 
        return {"ok": False, "error":"quota_exceeded", "retry_after": qt.get("retry_after_sec",30)}
    mid=_id_of(source)
    workdir=os.path.join(MEDIA_DIR, mid); os.makedirs(workdir, exist_ok=True)

    meta={}; subs=""; transcript=""
    if path:
        # lokalnyy fayl
        meta={"source":"file","path": path, "size": os.path.getsize(path) if os.path.isfile(path) else 0}
        pr=_ffprobe(path); 
        if pr.get("ok"): meta["ffprobe"]=pr["meta"]
        if prefer_subs:
            # if .wtt/.srt is nearby, we’ll take it
            base=os.path.splitext(path)[0]
            for ext in (".vtt",".srt"):
                p=base+ext
                if os.path.isfile(p):
                    subs=open(p,"r",encoding="utf-8",errors="ignore").read(); break
        if transcribe and not subs:
            transcript=_whisper_transcribe(path)
    else:
        # URL
        if not ALLOW_NET:
            return {"ok": False, "error":"network_disabled"}
        tmp=tempfile.mkdtemp(prefix="media_")
        try:
            info=_ytdlp_info(url or "", tmp)
            meta={"source":"url","url": url, "ytdlp": info.get("meta",{})}
            subs=info.get("subs","")
            # We don’t run fftests using media URLs; for short videos you can download audio, but we’ll leave it as is
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # Sokhranyaem subtitry/transkript
    subs_path=os.path.join(workdir,"subs.vtt")
    if subs.strip():
        open(subs_path,"w",encoding="utf-8").write(subs)
    tr_path=os.path.join(workdir,"transcript.txt")
    if transcript.strip():
        open(tr_path,"w",encoding="utf-8").write(transcript)

    # Chernovoy konspekt
    text_base = (subs or transcript)
    notes = _notes_from_text(text_base, 12) if text_base else ""
    notes_path=os.path.join(workdir,"notes.md")
    if notes:
        open(notes_path,"w",encoding="utf-8").write(notes)

    # Indeks
    j=_load(); items=j.get("items") or []
    rec={"id": mid, "created": int(time.time()), "source": source, "service": service, "meta": meta,
         "paths":{"dir": workdir, "subs": (subs_path if os.path.isfile(subs_path) else ""), "transcript": (tr_path if os.path.isfile(tr_path) else ""), "notes": (notes_path if os.path.isfile(notes_path) else "")}}
    # obnovim/vstavim
    items=[r for r in items if r.get("id")!=mid] + [rec]; j["items"]=items; _save(j)

    # Profilea, RAG, KG
    passport("media_ingest", {"id": mid, "service": service, "has_subs": bool(subs), "has_tr": bool(transcript)}, "media://ingest")
    if notes:
        rag_append(f"media-notes-{mid}", notes)
        kg_autolink([{"id": f"media-{mid}", "text": notes[:4000]}])

    return {"ok": True, "id": mid, "paths": rec["paths"], "service": service, "meta_small": {"has_subs": bool(subs), "has_transcript": bool(transcript)}}

def get(mid: str)->Dict[str,Any]:
    j=_load()
    for r in reversed(j.get("items") or []):
        if r.get("id")==mid:
            return {"ok": True, "item": r}
    return {"ok": False, "error":"not_found"}

def list_items(limit: int=50)->Dict[str,Any]:
    j=_load()
    lst=list(reversed(j.get("items") or []))[:max(1,int(limit))]
    return {"ok": True, "items": lst}

def status()->Dict[str,Any]:
    return {"ok": True, "ffprobe": bool(shutil.which(FFPROBE)), "ytdlp": bool(shutil.which(YTDLP)), "whisper": bool(shutil.which(WHISPER))}
# c=a+b