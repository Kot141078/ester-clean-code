# -*- coding: utf-8 -*-
"""modules/media/watchdog.py - votcher papok: nakhodit novye fayly, progonyaet cherez ingest.

Mosty:
- Yavnyy: (Avtonomiya ↔ Planirovschik) pozvolyaet Ester “samoy” podtyagivat kontent.
- Skrytyy #1: (Memory ↔ Profile) kazhdoe addavlenie kladetsya s edinym profileom.
- Skrytyy #2: (Inzheneriya ↔ Nadezhnost) vedem state.json, chtoby ne dublirovat.

Zemnoy abzats:
Kak konveyer: polozhil fayl v papku - on razobran i zanesen v pamyat.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CFG = os.path.join("data","media","watch_config.json")
STATE = os.path.join("data","media","watch_state.json")

def _load_json(p: str, dflt):
    try: return json.load(open(p,"r",encoding="utf-8"))
    except Exception: return dflt

def get_config() -> Dict[str,Any]:
    cfg=_load_json(CFG, {"dirs": (os.getenv("MEDIA_WATCH_DIRS","ingest,downloads").split(","))})
    return {"ok": True, **cfg}

def set_config(dirs: List[str]) -> Dict[str,Any]:
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    json.dump({"dirs": dirs}, open(CFG,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "dirs": dirs}

def _iter_files(d: str):
    for base,_,fs in os.walk(d):
        for fn in fs:
            if fn.lower().endswith((".mp4",".mkv",".mp3",".wav",".flac",".webm",".avi",".mov",".m4a",".ogg",".opus")):
                yield os.path.join(base, fn)

def tick(limit: int = 10) -> Dict[str,Any]:
    cfg=get_config(); st=_load_json(STATE, {"seen": {}})
    dirs=cfg.get("dirs") or []
    done=[]; errs=[]
    from modules.media.ingest import media_ingest  # lazy import
    for d in dirs:
        if not os.path.isdir(d): continue
        for p in _iter_files(d):
            if p in st["seen"]: continue
            try:
                rep=media_ingest(p, want_subtitles=True, want_stt=False, tags=["watch"])
                st["seen"][p]=int(time.time())
                done.append({"path": p, "ok": rep.get("ok",True), "draft_len": rep.get("draft_len",0)})
                if len(done)>=limit: break
            except Exception as e:
                errs.append({"path": p, "error": str(e)})
        if len(done)>=limit: break
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": len(errs)==0, "processed": done, "errors": errs}
# c=a+b