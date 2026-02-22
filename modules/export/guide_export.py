# -*- coding: utf-8 -*-
"""
modules/export/guide_export.py — eksport stsenariya v video-gayd.

Fayly:
- data/export/<name>/frame_0001.png ... — kadry
- data/export/<name>/guide.srt         — subtitry
- data/export/<name>/ffmpeg_win.bat    — komanda sborki (Windows)
- data/export/<name>/ffmpeg_unix.sh    — komanda sborki (Unix)

Kak rabotaet:
- Snimok ekrana cherez /desktop/rpa/screen.
- Esli peredan spisok shagov/podskazok — formiruem subtitry s taymkodom.
- Skladyvaem vse v papku; vozvraschaem put i arkhiv ZIP.

MOSTY:
- Yavnyy: (Deystviya ↔ Memory) prevraschaem zhivuyu sessiyu v material dlya obucheniya.
- Skrytyy #1: (Infoteoriya ↔ Reproduktsiya) PNG+SRT — perenosimaya forma, ne trebuet spets-PO.
- Skrytyy #2: (Kibernetika ↔ Kommunikatsiya) polzovatel mozhet delitsya gaydom oflayn.

ZEMNOY ABZATs:
Nikakogo ffmpeg vnutri; tolko skripty. Vse oflayn i lokalno.

# c=a+b
"""
from __future__ import annotations
import os, io, json, base64, zipfile, time, http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR = os.path.join(ROOT, "data", "export")
os.makedirs(DIR, exist_ok=True)

def _get(path: str) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _write(p: str, data: bytes):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f: f.write(data)

def _srt_time(ms: int) -> str:
    h = ms//3600000; ms%=3600000
    m = ms//60000; ms%=60000
    s = ms//1000; ms%=1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def export_current(name: str = "guide") -> dict:
    folder = os.path.join(DIR, name)
    os.makedirs(folder, exist_ok=True)

    # Kadr
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"): return {"ok": False, "error":"screen_failed"}
    b = base64.b64decode(scr.get("png_b64",""))
    _write(os.path.join(folder, "frame_0001.png"), b)

    # Mini-subtitry (odna podskazka)
    srt = "1\n00:00:00,000 --> 00:00:03,000\nDemonstratsiya: otkrytyy ekran Ester.\n"
    with open(os.path.join(folder, "guide.srt"), "w", encoding="utf-8") as f:
        f.write(srt)

    # Skripty
    with open(os.path.join(folder, "ffmpeg_unix.sh"), "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env bash\nffmpeg -framerate 1 -i frame_%04d.png -i guide.srt -c:v libx264 -pix_fmt yuv420p -c:s mov_text guide.mp4\n")
    with open(os.path.join(folder, "ffmpeg_win.bat"), "w", encoding="cp1251", errors="ignore") as f:
        f.write("ffmpeg -framerate 1 -i frame_%%04d.png -i guide.srt -c:v libx264 -pix_fmt yuv420p -c:s mov_text guide.mp4\r\n")

    # ZIP
    zpath = os.path.join(folder, "guide_bundle.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(folder):
            if fn.endswith(".zip"): continue
            z.write(os.path.join(folder, fn), arcname=fn)

    return {"ok": True, "folder": folder, "zip": zpath}