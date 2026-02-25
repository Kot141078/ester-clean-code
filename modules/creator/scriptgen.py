# -*- coding: utf-8 -*-
"""modules/creator/scriptgen.py - generatsiya stsenariya i storiborda (oflayn shablony).

Mosty:
- Yavnyy: (Creator ↔ Media) stsenariy → kadry → video.
- Skrytyy #1: (Passport ↔ Prozrachnost) otmechaem sozdanie stsenariev.
- Skrytyy #2: (Uploader ↔ Metadannye) iz stsenariya vyvodim zagolovki/tegi.

Zemnoy abzats:
Kak tetrad rezhissera: korotkiy “kryuchok”, punkty suti i prizyv - gotovyy plan dlya rolika.

# c=a+b"""
from __future__ import annotations
import os, json, time, math, re
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE=os.getenv("CREATOR_DIR","data/creator")
os.makedirs(BASE, exist_ok=True)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "creator://script")
    except Exception:
        pass

def gen_script(topic: str, style: str="shorts", duration: int=60)->Dict[str,Any]:
    """Returns a markdown-like script with HOOK/POINT/STA sections."""
    style=style.lower().strip()
    sec=max(10, min(300, int(duration or 60)))
    points=max(2, min(6, sec//15))
    tpl={
        "shorts": ("HOOK", "POINT", "CTA"),
        "tiktok": ("HOOK", "POINT", "CTA"),
        "youtube": ("INTRO", "SECTION", "OUTRO")
    }.get(style, ("HOOK","POINT","CTA"))
    lines=[f"[{tpl[0]}] {topic}: za {sec} sekund."]
    for i in range(1, points+1):
        lines.append(f"YuZF0ZZsch Step ZZF1ZZ: key idea on the topic “ZZF2ZZ”.")
    lines.append(f"YuZF0ZZsch Subscribe and watch the continuation.")
    script="\n".join(lines)
    path=os.path.join(BASE, f"script_{int(time.time())}.txt")
    open(path,"w",encoding="utf-8").write(script)
    _passport("creator_script", {"topic": topic, "style": style, "sec": sec})
    return {"ok": True, "script": script, "path": path, "points": points}

def storyboard(script: str, shots: int|None=None)->Dict[str,Any]:
    """We break the script into frames: each YuTAGshch is a frame; if not enough, padding to shots."""
    tags=re.findall(r"\\[(.*?)\\]", script)
    units=[s.strip() for s in re.split(r"\\[.*?\\]", script) if s.strip()]
    frames=[]
    for i,t in enumerate(tags):
        txt=units[i] if i < len(units) else ""
        frames.append({"i": i+1, "tag": t, "text": txt})
    if shots and shots>len(frames):
        for j in range(len(frames)+1, shots+1):
            frames.append({"i": j, "tag": "FILL", "text":"vizualnyy perebivochnyy kadr"})
    _passport("creator_storyboard", {"frames": len(frames)})
    return {"ok": True, "frames": frames}
# c=a+b