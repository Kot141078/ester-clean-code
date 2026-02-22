# -*- coding: utf-8 -*-
"""
modules/studio/pipelines.py — orkestratsiya payplaynov: idei→audio→video→pakety.

Mosty:
- Yavnyy: (Payplayn ↔ Modulnost) edinaya tochka «sdelat short/long» iz teksta/roley.
- Skrytyy #1: (Garazh/Flot ↔ Volya) planiruet zadachi i mozhet otdavat vo flot.
- Skrytyy #2: (Memory ↔ Profile) skladyvaet meta-otchet s profileom.

Zemnoy abzats:
Konveyer: na vkhod tekst i roli — na vykhod mp4+wav i metadannye dlya publikatsii.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def short_from_text(title: str, subs: List[Dict[str,Any]], bgm_path: str|None=None)->Dict[str,Any]:
    from modules.studio.video import render  # type: ignore
    return render(title=title, mode="short", aspect="9:16", text_subs=subs, bgm=bgm_path)

def long_from_drama(title: str, roles: List[Dict[str,Any]], script: List[Dict[str,Any]], bgm_path: str|None=None)->Dict[str,Any]:
    from modules.studio.tts import drama  # type: ignore
    from modules.studio.video import render  # type: ignore
    from modules.studio.prompts import _ensure as _ens  # type: ignore
    _ens()
    # shag 1: audio
    a=drama(title, roles, script)
    # shag 2: subtitry iz skripta (prostoe raspredelenie po 3s)
    subs=[]; t=0.0
    for line in script:
        txt=str(line.get("text",""))
        dur=max(1.5, min(6.0, len(txt)/10.0))
        subs.append({"t0": t, "t1": t+dur, "text": f"{line.get('role','')}: {txt}"})
        t+=dur
    # shag 3: video
    v=render(title=title, mode="long", aspect="16:9", duration=t, text_subs=subs, bgm=bgm_path or a.get("path"))
    # otchet
    rep={"ok": bool(a.get("ok")) and bool(v.get("ok")), "audio": a, "video": v, "subs": subs}
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, json.dumps(rep, ensure_ascii=False)[:4000], {"kind":"studio_long"}, source="studio://pipeline")
    except Exception:
        pass
    return rep
# c=a+b