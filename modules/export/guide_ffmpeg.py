# -*- coding: utf-8 -*-
"""modules/export/guide_ffmpeg.py - eksport v MP4 s lokalnym TTS (A/B-slot).

A/B-slot:
- A (by umolchaniyu): bez ozvuchki (mute), tolko video iz PNG.
- B: lokalnyy TTS cherez pyttsx3 (esli ustanovlen), generiruetsya WAV/MP3 i ispolzuetsya v skriptakh.

ENV:
- ESTER_TTS_MODE = "A" | "B"

Vykhod:
- data/export/<name>/frames/frame_%04d.png — istochnik kadrov (esli net, sozdadim 1 screenshot)
- data/export/<name>/voice.wav (i/ili voice.mp3)
- data/export/<name>/make_unix.sh / make_win.bat — ffmpeg komandy
- data/export/<name>/guide.mp4 — itog (post zapuska skripta polzovatelem)

MOSTY:
- Yavnyy: (Memory ↔ Kommunikatsiya) iz sessii - gotovyy MP4.
- Skrytyy #1: (Infoteoriya ↔ Determinizm) yavnye skripty sborki, rabotayut oflayn.
- Skrytyy #2: (Inzheneriya ↔ Dostupnost) TTS lokalnyy i optsionalnyy.

ZEMNOY ABZATs:
Nothing wrong with oblaka. Esli pyttsx3 nedostupen - tikho rabotaem v rezhime A.

# c=a+b"""
from __future__ import annotations
import os, io, json, base64, wave, struct
import http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "export")
os.makedirs(DIR, exist_ok=True)

def _get(path: str) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=15.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _ensure_frame(dirn: str) -> None:
    fdir = os.path.join(dirn, "frames"); os.makedirs(fdir, exist_ok=True)
    # if there are no frames, make one from the current screen
    if not any(n for n in os.listdir(fdir) if n.endswith(".png")):
        scr = _get("/desktop/rpa/screen")
        if not scr.get("ok"): return
        with open(os.path.join(fdir, "frame_0001.png"), "wb") as f:
            f.write(base64.b64decode(scr.get("png_b64","").encode("ascii")))

def _write(p: str, data: bytes):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f: f.write(data)

def _tts_local(text: str, out_wav: str) -> bool:
    # Slot B: pittx3, if available
    mode = os.environ.get("ESTER_TTS_MODE", "A").upper()
    if mode != "B":
        return False
    try:
        import pyttsx3  # type: ignore
    except Exception:
        return False
    try:
        eng = pyttsx3.init()
        eng.save_to_file(text or " ", out_wav)
        eng.runAndWait()
        return True
    except Exception:
        return False

def make(name: str, text: str = "") -> dict:
    folder = os.path.join(DIR, name); os.makedirs(folder, exist_ok=True)
    _ensure_frame(folder)

    # TTS (optional)
    voice = None
    wav = os.path.join(folder, "voice.wav")
    if _tts_local(text, wav):
        voice = "voice.wav"

    # skripty ffmpeg
    mk_unix = os.path.join(folder, "make_unix.sh")
    mk_win  = os.path.join(folder, "make_win.bat")
    with open(mk_unix, "w", encoding="utf-8") as f:
        if voice:
            f.write("#!/usr/bin/env bash\nffmpeg -framerate 1 -i frames/frame_%04d.png -i voice.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac guide.mp4")
        else:
            f.write("#!/usr/bin/env bash\nffmpeg -framerate 1 -i frames/frame_%04d.png -c:v libx264 -pix_fmt yuv420p guide.mp4\n")
    with open(mk_win, "w", encoding="cp1251", errors="ignore") as f:
        if voice:
            f.write("ffmpeg -framerate 1 -i frames\\frame_%%04d.png -i voice.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac guide.mp4\r\n")
        else:
            f.write("ffmpeg -framerate 1 -i frames\\frame_%%04d.png -c:v libx264 -pix_fmt yuv420p guide.mp4\r\n")

    return {"ok": True, "folder": folder, "voice": bool(voice), "scripts": {"unix": mk_unix, "win": mk_win}}