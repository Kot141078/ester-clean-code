# -*- coding: utf-8 -*-
"""modules/video/extractors/mkv_tools.py - rabota s MKV: spisok dorozhek, izvlechenie sabov s uchetom yazyka.

Funktsii:
  • list_tracks(path:str) -> {"subs":[{"index":i,"lang":"ru|en|...","codec":...}], "audio":[...]}
  • extract_best_subs(path:str, lang_pref:list[str]) -> Optional[str] # put k .srt/.ass

Mosty:
- Yavnyy: (Inzheneriya ↔ Video) pravilno vybiraem nuzhnuyu sab-dorozhku v multitrekovom konteynere.
- Skrytyy #1: (Infoteoriya ↔ Kachestvo) otdaem predpochtenie tekstovym subtitram (srt/ass), ne bitmap.
- Skrytyy #2: (Kibernetika ↔ Volya) ispolzuem poryadok yazykov iz ENV/konfiga.

Zemnoy abzats:
Eto "schiptsy dlya MKV": akkuratno vytaschit pravilnye subtitry iz banki, esli oni tam est.

# c=a+b"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")

def _run(cmd, timeout=30.0):
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        return p.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")
    except Exception as e:
        return -1, "", str(e)

def list_tracks(path: str) -> Dict[str, Any]:
    code, out, err = _run([FFPROBE, "-v", "quiet", "-print_format", "json", "-show_streams", path], timeout=20.0)
    if code != 0 or not out.strip():
        return {"subs": [], "audio": []}
    try:
        j = json.loads(out)
    except Exception:
        j = {}
    subs = []
    audio = []
    for s in (j.get("streams") or []):
        if s.get("codec_type") == "subtitle":
            subs.append({
                "index": s.get("index"),
                "lang": (s.get("tags") or {}).get("language") or "",
                "codec": s.get("codec_name")
            })
        if s.get("codec_type") == "audio":
            audio.append({
                "index": s.get("index"),
                "lang": (s.get("tags") or {}).get("language") or "",
                "codec": s.get("codec_name")
            })
    return {"subs": subs, "audio": audio}

_TEXT_CODECS = {"subrip", "ass", "srt", "ssa", "webvtt"}

def extract_best_subs(path: str, lang_pref: List[str]) -> Optional[str]:
    tracks = list_tracks(path).get("subs") or []
    # first text, then by language
    def rank(t):
        score = 0
        if (t.get("codec") or "").lower() in _TEXT_CODECS:
            score += 2
        lang = (t.get("lang") or "").lower()
        for i, lp in enumerate(lang_pref):
            if lp and lang.startswith(lp.lower()):
                score += (len(lang_pref) - i)
                break
        return score
    tracks.sort(key=rank, reverse=True)
    if not tracks:
        return None
    best = tracks[0]
    out_path = os.path.splitext(path)[0] + f".extract.{best.get('lang') or 'xx'}.srt"
    code, out, err = _run([FFMPEG, "-y", "-i", path, "-map", f"0:{best['index']}", out_path], timeout=90.0)
    if code == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
        return out_path
# return None