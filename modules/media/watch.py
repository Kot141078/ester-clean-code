# -*- coding: utf-8 -*-
"""
modules/media/watch.py — konfiguriruemyy votcher direktoriy/spiskov URL.

Mosty:
- Yavnyy: (Planirovschik ↔ Media) odin «tik» obrabatyvaet nemnogo zadach.
- Skrytyy #1: (Volya ↔ Eksheny) dostupen kak deystvie media.watch.tick.
- Skrytyy #2: (Kvoty ↔ Backpressure) kazhdyy tik uvazhaet limity ingest.

Zemnoy abzats:
Periodicheski zaglyadyvaem v papki i spiski ssylok — i berezhno proglatyvaem novye roliki.

# c=a+b
"""
from __future__ import annotations
import os, json, time, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CFG=os.getenv("MEDIA_WATCH_CFG","data/media/watch.json")

DEFAULT={"watch_dirs":["/data/inbox","data/inbox"], "watch_urls":[], "max_per_tick":2}

def _ensure():
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    if not os.path.isfile(CFG):
        json.dump(DEFAULT, open(CFG,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def load_cfg(): _ensure(); return json.load(open(CFG,"r",encoding="utf-8"))

def tick()->dict:
    from modules.media.ingest import ingest  # type: ignore
    cfg=load_cfg()
    done=[]; skipped=[]; errs=[]
    left=int(cfg.get("max_per_tick",2))
    # 1) direktorii
    for d in cfg.get("watch_dirs",[]):
        if left<=0: break
        if not os.path.isdir(d): continue
        for fn in sorted(os.listdir(d))[:left]:
            p=os.path.join(d,fn)
            if os.path.isfile(p) and re.search(r"\.(mp4|mkv|webm|mp3|m4a|mov|avi)$", fn, re.I):
                try:
                    rep=ingest(p, want_subtitles=True, want_stt=False, tags=["watch"])
                    if rep.get("ok"): done.append({"src":p,"id":rep.get("id")}); left-=1
                    else: errs.append({"src":p,"error": rep.get("error")})
                except Exception as e:
                    errs.append({"src":p,"error":str(e)})
    # 2) URL-spisok
    for url in cfg.get("watch_urls",[]):
        if left<=0: break
        try:
            rep=ingest(url, want_subtitles=True, want_stt=False, tags=["watch"])
            if rep.get("ok"): done.append({"src":url,"id":rep.get("id")}); left-=1
            else: errs.append({"src":url,"error": rep.get("error")})
        except Exception as e:
            errs.append({"src":url,"error":str(e)})
    return {"ok": len(errs)==0, "done": done, "skipped": skipped, "errors": errs}
# c=a+b