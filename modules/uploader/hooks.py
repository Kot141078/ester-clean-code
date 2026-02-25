# -*- coding: utf-8 -*-
"""modules/uploader/hooks.py — podgotovka metadannykh dlya TikTok/YouTube/Patreon.

Mosty:
- Yavnyy: (Creator ↔ Ploschadki) vydaem zagolovok, opisanie, tegi, prevyu.
- Skrytyy #1: (Passport ↔ Prozrachnost) fiksiruem shablony/vybor platformy.
- Skrytyy #2: (Portfolio ↔ Navigatsiya) mozhno add ssylku na portfolio.

Zemnoy abzats:
Eto kak brief: ploschadka zhdet konkretnye polya - my ikh gotovim iz stsenariya i shablonov.

# c=a+b"""
from __future__ import annotations
import os, json, re, time, hashlib
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TPL=os.getenv("UPLOAD_TEMPLATES","data/uploader/templates.json")
os.makedirs(os.path.dirname(TPL), exist_ok=True)
if not os.path.isfile(TPL):
    json.dump({
        "youtube":{"title":"{hook} | {topic}","tags":["ai","ester","tutorial"],"desc":"{body}\n\n#ai #ester"},
        "tiktok":{"title":"{hook}","tags":["ai","ester"],"desc":"{body}"},
        "patreon":{"title":"ZZF0Z - extended version","tags":["behind-the-scenes"],"desc":"{body}"}
    }, open(TPL,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "uploader://meta")
    except Exception:
        pass

def _parse(script: str)->Dict[str,str]:
    m=re.search(r"\\[(HOOK|INTRO)\\]\\s*(.+)", script, flags=re.I)
    hook=(m.group(2).strip() if m else "Korotko o glavnom")
    topic=re.sub(r"^.*?:","", hook).strip() or "Tema"
    return {"hook": hook, "topic": topic, "body": script}

def prepare(script: str, platform: str="youtube")->Dict[str,Any]:
    platform=platform.lower().strip()
    tpl=json.load(open(TPL,"r",encoding="utf-8")).get(platform) or json.load(open(TPL,"r",encoding="utf-8")).get("youtube")
    parts=_parse(script)
    title=tpl.get("title","{topic}").format(**parts)
    tags=tpl.get("tags",[])
    desc=tpl.get("desc","{body}").format(**parts)
    thumb="data/creator/thumb_"+hashlib.sha256(script.encode("utf-8")).hexdigest()[:8]+".png"
    # simple preview plug
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        os.makedirs(os.path.dirname(thumb), exist_ok=True)
        img=Image.new("RGB",(1280,720),(20,20,20))
        dr=ImageDraw.Draw(img); dr.text((40,340), title[:40], fill=(220,220,220))
        img.save(thumb)
    except Exception:
        # bez pillow — pustoy fayl
        open(thumb,"wb").write(b"")
    _passport("uploader_prepare", {"platform": platform})
    return {"ok": True, "platform": platform, "title": title, "tags": tags, "description": desc, "thumbnail": thumb}
# c=a+b