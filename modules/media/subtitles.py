# -*- coding: utf-8 -*-
"""
modules/media/subtitles.py — izvlechenie subtitrov: iz URL (cherez yt-dlp), iz fayla (vstroennye dorozhki ffmpeg), normalizatsiya .srt.

Mosty:
- Yavnyy: (Kontent ↔ Tekst) poluchaem tekstovuyu dorozhku dlya analiza.
- Skrytyy #1: (Infoteoriya ↔ Normalizatsiya) privodim k .srt/.txt, chistim taymkody.
- Skrytyy #2: (Memory ↔ Profile) vozvraschaem sha/put dlya dalneyshego inzhesta.

Zemnoy abzats:
Vytaschit subtitry — znachit dat mozgam tekst: dalshe mozhno konspektirovat.

# c=a+b
"""
from __future__ import annotations
import os, re, subprocess, hashlib, json
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEDIA_DIR = os.getenv("MEDIA_DIR","data/media")
FFMPEG = os.getenv("FFMPEG_BIN","ffmpeg")

def _sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""):
            h.update(ch)
    return h.hexdigest()

def _normalize_srt(path: str) -> Dict[str,Any]:
    try:
        raw = open(path,"r",encoding="utf-8",errors="ignore").read()
        # legkaya chistka lishnikh probelov
        raw = re.sub(r"\r","", raw)
        return {"ok": True, "path": path, "sha256": _sha256(path), "lines": len(raw.strip().splitlines())}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def from_file(path: str, prefer_lang: str | None = None) -> Dict[str,Any]:
    if not os.path.isfile(path): return {"ok": False, "error":"not_found"}
    base, _ = os.path.splitext(path)
    out = base + f".{prefer_lang or 'sub'}.srt"
    # popytka izvlech pervuyu subtitrovuyu dorozhku
    try:
        args = [FFMPEG, "-y", "-i", path, "-map", "0:s:0", out]
        if prefer_lang:
            # filtr po yazyku (best-effort): ffmpeg sam podberet pervuyu, sootvetstvuyuschuyu lang
            args = [FFMPEG, "-y", "-i", path, "-map", "0:s:m:language:"+prefer_lang, out]
        r = subprocess.run(args, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            # ne vyshlo — vozmozhno net subtitrov
            return {"ok": False, "error":"no_sub_stream"}
        return _normalize_srt(out)
    except FileNotFoundError:
        return {"ok": False, "error":"ffmpeg_missing"}

def from_url(url: str, prefer_lang: str | None = None) -> Dict[str,Any]:
    try:
        from modules.media.yt_dlp_wrapper import fetch  # type: ignore
    except Exception:
        return {"ok": False, "error":"yt_dlp_unavailable"}
    rep = fetch(url, prefer_subs_lang=prefer_lang or "en")
    if not rep.get("ok"): return rep
    # yt-dlp obychno kladet .srt ryadom; naydem
    dirn = os.path.dirname(rep["path"])
    stem = os.path.splitext(os.path.basename(rep["path"]))[0]
    candidates = [os.path.join(dirn, f) for f in os.listdir(dirn) if f.startswith(stem) and f.endswith(".srt")]
    if not candidates:
        # popytaemsya izvlech iz fayla
        return from_file(rep["path"], prefer_lang)
    # vozmem pervyy .srt
    candidates.sort(key=os.path.getmtime)
    return _normalize_srt(candidates[-1])
# c=a+b