# -*- coding: utf-8 -*-
"""
modules/video/extractors/iso_tools.py — bezopasnyy skaner DVD/ISO (best-effort, bez montirovaniya).

Funktsii:
  • is_dvd_folder(path:str) -> bool          # raspoznaet VIDEO_TS struktura
  • scan_vob_files(path:str) -> list[str]    # osnovnye VOB'y filma
  • try_extract_dvd_subs(path:str, lang_pref:list[str]) -> Optional[str]   # popytka vytaschit tekstovye saby

Mosty:
- Yavnyy: (Inzheneriya ↔ Video) podderzhka starykh arkhivov (DVD) bez root i montirovaniya.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) esli saby bitmap — chestno vozvraschaem None (bez OCR).
- Skrytyy #2: (Kibernetika ↔ Volya) integriruetsya v universalnyy konveyer kak odna iz vetok.

Zemnoy abzats:
Eto «fonarik dlya starykh korobok»: podsvetili VIDEO_TS, nashli VOB — esli povezet, vytaschili tekstovye saby.

# c=a+b
"""
from __future__ import annotations

import glob
import os
import subprocess
from typing import List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")

def is_dvd_folder(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    names = {n.lower() for n in os.listdir(path)}
    return "video_ts" in names or any(n.startswith("vts_") and n.endswith(".vob") for n in names)

def scan_vob_files(path: str) -> List[str]:
    files = []
    if os.path.isdir(path):
        files = glob.glob(os.path.join(path, "*.VOB")) + glob.glob(os.path.join(path, "*.vob"))
    return sorted(files)

def try_extract_dvd_subs(path: str, lang_pref: List[str]) -> Optional[str]:
    # U DVD chasche bitmap subtitry (VobSub) → ffmpeg vydast .sub/.idx (bez OCR) — vernem None.
    # Esli vdrug tekstovye — poprobuem izvlech pervuyu podkhodyaschuyu dorozhku.
    vobs = scan_vob_files(path)
    if not vobs:
        return None
    # poprobuem pervuyu bolshuyu
    candidate = max(vobs, key=lambda p: os.path.getsize(p))
    # na DVD subtitry obychno bitmap → vozvraschaem None, ostavlyaya vozmozhnost vneshnego OCR
    # (osoznannoe ogranichenie bez tyazhelykh zavisimostey)
# return None