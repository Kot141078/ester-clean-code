# -*- coding: utf-8 -*-
"""modules/media/probe.py - bezopasnaya “proba” video/audio (lokalno/onlayn).

Mosty:
- Yavnyy: (Inzheneriya ↔ Media) vynimaem dlitelnost/kodeki/saby, ne kachaya lishnego.
- Skrytyy #1: (Ekonomika ↔ Ingest Quotas) proveryaem baket pered tyazhelymi shagami.
- Skrytyy #2: (Memory/KG ↔ RAG) vozvraschaem passport-atributy dlya dalneyshego index.

Zemnoy abzats:
Kak tekhnik s fonarikom: bystro posmotret “what is there” v rolike i stoit li ego glotat.

# c=a+b"""
from __future__ import annotations
import os, json, re, subprocess, shutil, hashlib, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEDIA_ROOT = os.getenv("MEDIA_ROOT","data/media/store")
LANGS = [x.strip() for x in (os.getenv("MEDIA_LANGS","en,ru") or "en,ru").split(",") if x.strip()]

def _sha(s:str)->str: return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _cmd_exists(x:str)->bool: return shutil.which(x) is not None

def _run(cmd:list[str], timeout:int=20)->Dict[str,Any]:
    try:
        p=subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err=p.communicate(timeout=timeout)
        return {"ok": p.returncode==0, "stdout": out, "stderr": err, "rc": p.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _ffprobe(path:str)->Dict[str,Any]:
    if not _cmd_exists("ffprobe") or (not os.path.exists(path)):
        return {"ok": False, "error":"ffprobe_missing_or_path"}
    cmd=["ffprobe","-v","error","-print_format","json","-show_format","-show_streams",path]
    rep=_run(cmd, timeout=25)
    if rep.get("ok"):
        try: return {"ok": True, **json.loads(rep["stdout"])}
        except Exception: return {"ok": True, "raw": rep["stdout"]}
    return rep

def _ytdlp_info(url:str)->Dict[str,Any]:
    if not _cmd_exists("yt-dlp"):
        return {"ok": False, "error":"yt-dlp_missing"}
    cmd=["yt-dlp","-J","--no-warnings","--skip-download","--no-call-home",
         "--write-sub","--write-auto-sub","--sub-lang", ",".join(LANGS), url]
    rep=_run(cmd, timeout=60)
    if rep.get("ok"):
        try: return {"ok": True, "info": json.loads(rep["stdout"])}
        except Exception: return {"ok": True, "raw": rep["stdout"]}
    return rep

def probe(path_or_url:str)->Dict[str,Any]:
    s=str(path_or_url or "")
    is_url=bool(re.match(r"^https?://", s))
    if is_url:
        info=_ytdlp_info(s)
        meta={"source":"url","url":s}
        if info.get("ok") and "info" in info:
            i=info["info"]
            meta.update({
                "title": i.get("title"), "duration": i.get("duration"),
                "uploader": i.get("uploader"), "channel": i.get("channel"),
                "webpage_url": i.get("webpage_url"), "subtitles": bool(i.get("subtitles") or i.get("automatic_captions"))
            })
        meta["sha256"]= _sha(s)
        return {"ok": True, "meta": meta, "tools":{"yt-dlp": _cmd_exists("yt-dlp")}}
    else:
        p=os.path.abspath(s)
        ff=_ffprobe(p)
        meta={"source":"file","path": p, "sha256": _sha(f"file://{p}")}
        if ff.get("ok") and ("format" in ff or "raw" in ff):
            if "format" in ff:
                f=ff["format"]; meta.update({"duration": float(f.get("duration",0.0)), "size": int(f.get("size",0))})
            v=[x for x in ff.get("streams",[]) if x.get("codec_type")=="video"]
            a=[x for x in ff.get("streams",[]) if x.get("codec_type")=="audio"]
            meta.update({"video_streams": len(v), "audio_streams": len(a)})
        return {"ok": True, "meta": meta, "tools":{"ffprobe": _cmd_exists("ffprobe")}}
# c=a+b