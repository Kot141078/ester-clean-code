# -*- coding: utf-8 -*-
"""modules/video/subtitles/lang_detect.py - legkiy detector yazyka dlya subtitrov/teksta (bez vneshnikh bibliotek).

Funktsii:
  • detect_lang(text:str, top_n:int=1) -> {"lang":"ru|en|unknown","conf":0..1}
  • detect_lang_file(path:str, limit_bytes:int=200000) -> {...}

Evristiki:
  • Doli kirillitsy/latinitsy + chastotnye slova (i/v/na/the/and/of) → prostaya veroyatnostnaya otsenka.

Mosty:
- Yavnyy: (Memory ↔ Video) podbiraem pravilnye dorozhki i saydkary bez ruchnogo vybora.
- Skrytyy #1: (Infoteoriya ↔ Kachestvo) filtruem “ne tot yazyk”, umenshaya noise v indeksatsii.
- Skrytyy #2: (Kibernetika ↔ Volya) pravila myshleniya mogut vybirat yazyk konfigom.

Zemnoy abzats:
Eto “nyukhach yazyka”: glyanul na paru abzatsev - ponyal, russkiy eto ili angliyskiy, i vzyal podkhodyaschie saby.

# c=a+b"""
from __future__ import annotations

import os
import re
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

RU_COMMON = {"i", "v", "ne", "na", "chto", "eto", "kak", "s", "po", "no", "a", "k"}
EN_COMMON = {"the", "and", "of", "to", "in", "is", "that", "it", "for", "on"}

def detect_lang(text: str, top_n: int = 1) -> Dict[str, float | str]:
    s = (text or "")[:200000].lower()
    if not s.strip():
        return {"lang": "unknown", "conf": 0.0}
    cyr = len(re.findall(r"[a-yae]", s))
    lat = len(re.findall(r"[a-z]", s))
    total = max(1, cyr + lat)
    p_ru = cyr / total
    p_en = lat / total
    # frequency words (very rude)
    tokens = re.findall(r"[a-za-yae]+", s)
    if any(t in RU_COMMON for t in tokens[:2000]):
        p_ru += 0.1
    if any(t in EN_COMMON for t in tokens[:2000]):
        p_en += 0.1
    if p_ru > p_en and p_ru > 0.55:
        return {"lang": "ru", "conf": min(1.0, p_ru)}
    if p_en > p_ru and p_en > 0.55:
        return {"lang": "en", "conf": min(1.0, p_en)}
    return {"lang": "unknown", "conf": max(p_ru, p_en)}

def detect_lang_file(path: str, limit_bytes: int = 200000) -> Dict[str, float | str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            chunk = f.read(limit_bytes)
        return detect_lang(chunk)
    except Exception:
        return {"lang": "unknown", "conf": 0.0}
