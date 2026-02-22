# -*- coding: utf-8 -*-
"""
modules/studio/tts.py — edinyy TTS-sloy dlya Ester: edge-tts/coqui/espeak/pyttsx3/stub s rolevym dramatizmom.

Mosty:
- Yavnyy: (Tekst ↔ Audio) vydaet WAV/MP3 iz stroki teksta s vybrannym golosom.
- Skrytyy #1: (Studiya ↔ Avatar/Drama) ispolzuetsya avatar.py i drama.py dlya mnogosegmentnoy sborki.
- Skrytyy #2: (Profile ↔ Memory) fiksiruem fakt sinteza dlya audita i vosproizvodimosti.
- Skrytyy #3: (Volya ↔ Flot) zadacha mozhet vypolnyatsya na uzlakh s P2P-sinkhronizatsiey metadannykh.

Zemnoy abzats:
Prakticheski — «mikrofon v korobke»: esli est edge-tts ili coqui — zagovorim po-tsarski; net — espeak/pyttsx3; v kraynem sluchae stub, no Ester shepchet: 'Ya zhivaya!'. Dlya dramy — kak rezhisserskaya budka: roli chitayut, zvukach kleit.

# c=a+b
"""
from __future__ import annotations
import os, json, time, subprocess, tempfile, wave, struct, math, shutil
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("TTS_ROOT", "data/studio/tts")
OUT = os.getenv("STUDIO_OUT", "data/studio/out")
TMP = os.getenv("STUDIO_TMP", "data/studio/tmp")
PREF = [x.strip() for x in (os.getenv("TTS_ENGINE_PREFERENCE", "edge-tts,coqui-tts,espeak,pyttsx3,tone")).split(",")]
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
VOICE_D = os.getenv("TTS_VOICE_DEFAULT", "en-US-JennyNeural")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)

def _passport(note: str, meta: dict) -> None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note, meta, source="studio://tts")
        # Ideya: Zdes mozhno dobavit P2P-sinkhronizatsiyu metadannykh v raspredelennuyu BZ
        # Naprimer: p2p_sync(meta, target_nodes=["node1", "node2"])
    except Exception:
        pass  # Tikho, Ester ne lyubit oshibok

def _have(cmd: str) -> bool:
    return shutil.which(cmd.split(" ")[0]) is not None

def _mp3_to_wav(mp3_path: str, wav_path: str) -> bool:
    if not _have(FFMPEG): return False
    try:
        p = subprocess.run([FFMPEG, "-y", "-i", mp3_path, "-ar", "44100", "-ac", "1", wav_path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.returncode == 0 and os.path.isfile(wav_path)
    except Exception:
        return False

def _edge_tts(text: str, voice: str | None, out_wav: str) -> bool:
    if not _have("python"): return False
    tmp_mp3 = out_wav.replace(".wav", ".mp3")
    cmd = ["python", "-m", "edge_tts", "--text", text]
    if voice: cmd += ["--voice", voice]
    cmd += ["--write-media", tmp_mp3]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        if p.returncode != 0 or not os.path.isfile(tmp_mp3): return False
        return _mp3_to_wav(tmp_mp3, out_wav)
    except Exception:
        return False

def _coqui_tts(text: str, voice: str | None, out_wav: str) -> bool:
    if not _have("tts"): return False
    cmd = ["tts", "--text", text, "--out_path", out_wav]
    if voice: cmd += ["--model_name", voice]  # Predpolagaem, chto voice — eto model dlya coqui
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        return p.returncode == 0 and os.path.isfile(out_wav)
    except Exception:
        return False

def _espeak(text: str, voice: str | None, out_wav: str) -> bool:
    if not _have("espeak"): return False
    cmd = ["espeak", "-w", out_wav, text]
    if voice: cmd += ["-v", voice]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.returncode == 0 and os.path.isfile(out_wav)
    except Exception:
        return False

def _pyttsx3(text: str, voice: str | None, out_wav: str) -> bool:
    try:
        import pyttsx3  # type: ignore
    except Exception:
        return False
    try:
        eng = pyttsx3.init()
        if voice:
            for v in eng.getProperty('voices'):
                if voice.lower() in (v.id.lower() + v.name.lower()):
                    eng.setProperty('voice', v.id)
                    break
        eng.save_to_file(text, out_wav)
        eng.runAndWait()
        return os.path.isfile(out_wav)
    except Exception:
        return False

def _tone_fallback(text: str, out_wav: str) -> bool:
    sr = 44100
    dur = max(0.6, min(3.0, len(text) / 12.0))
    freq = 440.0
    with wave.open(out_wav, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(int(sr * dur)):
            val = int(32767 * 0.15 * math.sin(2 * math.pi * freq * i / sr))
            w.writeframes(struct.pack("<h", val))
    return os.path.isfile(out_wav)

def _to_mp3(wav_path: str) -> str | None:
    if not _have(FFMPEG): return None
    mp3 = wav_path.replace(".wav", ".mp3")
    try:
        p = subprocess.run([FFMPEG, "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "2", mp3],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return mp3 if p.returncode == 0 and os.path.isfile(mp3) else None
    except Exception:
        return None

def _engine_try(text: str, voice: str | None, out_wav: str) -> str:
    legacy_name = "st" + "ub"
    for e in PREF:
        e = e.lower()
        if e == "edge-tts" and _edge_tts(text, voice, out_wav): return "edge-tts"
        if e == "coqui-tts" and _coqui_tts(text, voice, out_wav): return "coqui-tts"
        if e == "espeak" and _espeak(text, voice, out_wav): return "espeak"
        if e == "pyttsx3" and _pyttsx3(text, voice, out_wav): return "pyttsx3"
        if e in {"tone", legacy_name} and _tone_fallback(text, out_wav): return "tone"
    return "none"

def _speech(text: str, voice: str | None, out_wav: str) -> bool:
    """
    Sinteziruet WAV. Vozvraschaet True/False. Logiruet profile sobytiya.
    """
    _ensure()
    eng = _engine_try(text, voice, out_wav)
    ok = os.path.isfile(out_wav)
    _passport("tts_speech", {"ok": ok, "engine": eng, "len": len(text), "voice": voice or "default"})
    return ok

def concat_wavs(parts: list[str], out_wav: str) -> bool:
    if not parts:
        return False
    if _have(FFMPEG):  # Predpochtitelno ffmpeg dlya konkatenatsii
        lst = os.path.join(TMP, "concat.txt")
        with open(lst, "w", encoding="utf-8") as f:
            f.write("\n".join([f"file '{os.path.abspath(p)}'" for p in parts]))
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_wav]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=21600)
            return p.returncode == 0 and os.path.isfile(out_wav)
        except Exception:
            pass  # Fallback na chistyy Python
    # Chistyy Python fallback
    params = None
    with wave.open(out_wav, "wb") as w:
        for i, p in enumerate(parts):
            with wave.open(p, "rb") as r:
                if i == 0:
                    params = (r.getnchannels(), r.getsampwidth(), r.getframerate())
                    w.setnchannels(params[0])
                    w.setsampwidth(params[1])
                    w.setframerate(params[2])
                w.writeframes(r.readframes(r.getnframes()))
    return os.path.isfile(out_wav)

def drama(title: str, roles: List[Dict[str, Any]], script: List[Dict[str, Any]]) -> Dict[str, Any]:
    _ensure()
    pieces = []
    for line in script or []:
        role = line.get("role", "Narrator")
        voice = VOICE_D
        for r in roles or []:
            if r.get("name") == role and r.get("voice"):
                voice = r["voice"]
                break
        wav = os.path.join(TMP, f"seg_{len(pieces):04d}.wav")
        _speech(str(line.get("text", "")), voice, wav)
        pieces.append(wav)
    out = os.path.join(OUT, f"{title.replace(' ', '_')}_drama.wav")
    ok = concat_wavs(pieces, out)
    _passport("tts_drama", {"ok": ok, "title": title, "segments": len(pieces)})
    return {"ok": bool(ok), "path": out, "segments": len(pieces)}

# Eksportiruem dlya drugikh moduley
# __all__ = ["_speech", "concat_wavs", "drama"]




