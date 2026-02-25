# -*- coding: utf-8 -*-
"""modules/video/extractors/providers.py - edinyy sloy klassifikatsii URL i polucheniya metadannykh/sabov cherez yt-dlp.

Funktsii:
  • classify_url(url:str) -> {"provider": "...", "host": "..."}
  • yt_info(url:str) -> dict # metadannye (bez skachivaniya media)
  • yt_subs(url:str, lang:str|None) -> Optional[str] # put k .vtt sabam (temp) libo None

Mosty:
- Yavnyy: (Inzheneriya ↔ Video) odna tochka integratsii dlya vsekh onlayn-provayderov.
- Skrytyy #1: (Infoteoriya ↔ Masshtab) maksimalno ispolzuem vstroennye parsery yt-dlp (mnogo saytov bez koda).
- Skrytyy #2: (Kibernetika ↔ Volya) universalnyy layer pozvolyaet pravilam myshleniya ne zaviset ot konkretnogo sayta.

Zemnoy abzats:
This is “universalnyy perekhodnik”: nevazhno, YouTube/Vimeo/RuTube - na vykhode odinakovaya shina dannykh.

# c=a+b"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")
os.makedirs(DATA_DIR, exist_ok=True)

YTDLP = os.getenv("YTDLP_BIN", "yt-dlp")

def _run(cmd, timeout=30.0):
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        return p.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")
    except Exception as e:
        return -1, "", str(e)

def classify_url(url: str) -> Dict[str, str]:
    host = ""
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        pass
    provider = "generic"
    if "youtube." in host or "youtu.be" in host:
        provider = "youtube"
    elif "vimeo.com" in host:
        provider = "vimeo"
    elif "rutube.ru" in host:
        provider = "rutube"
    return {"provider": provider, "host": host}

def yt_info(url: str) -> Dict[str, Any]:
    code, out, err = _run([YTDLP, "-J", "--no-warnings", "--skip-download", url], timeout=40.0)
    if code == 0 and out.strip():
        try:
            return json.loads(out) or {}
        except Exception:
            pass
    try:
        import yt_dlp  # type: ignore
        with yt_dlp.YoutubeDL({"skip_download": True, "quiet": True}) as y:
            info = y.extract_info(url, download=False)
            return info or {}
    except Exception:
        return {}

def yt_subs(url: str, lang: Optional[str]) -> Optional[str]:
    out_dir = os.path.join(DATA_DIR, "tmp_subs")
    os.makedirs(out_dir, exist_ok=True)
    args = [YTDLP, "--no-warnings", "--skip-download", "--sub-format", "vtt", "-o", os.path.join(out_dir, "%(id)s.%(ext)s")]
    # first auto-subs, then regular ones
    for auto_flag in (["--write-auto-sub"], ["--write-subs"]):
        cmd = [*args, *auto_flag]
        if lang:
            cmd += ["--sub-lang", lang]
        code, out, err = _run(cmd, timeout=80.0)
        if code == 0:
            vtts = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".vtt")]
            if vtts:
                return vtts[0]
# return None