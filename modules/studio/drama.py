# -*- coding: utf-8 -*-
"""modules/studio/drama.py - audiodrama “po rolyam”: stsenariy → TTS-segmenty → svedenie + SRT.

Mosty:
- Yavnyy: (Stsenariy ↔ Audio) daet gotovuyu dorozhku i subtitry s razmetkoy roley.
- Skrytyy #1: (TTS ↔ Sotsdeploy/Studiya) ispolzuet obschee yadro TTS i mozhet idti dalshe v upload-kit.
- Skrytyy #2: (Profile ↔ Memory) sokhranyaet profile sborki (taymingi, roli, puti).

Zemnoy abzats:
Inzhenerno eto “malenkaya studiya”: kazhduyu repliku ozvuchili podkhodyaschim golosom, add pauzy, skleili i vygruzili subtitry.

# c=a+b"""
from __future__ import annotations
import os, json, time, wave, struct
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT = os.getenv("DRAMA_OUT","data/studio/drama")
FFMPEG = os.getenv("FFMPEG_BIN","ffmpeg")

def _ensure():
    os.makedirs(OUT, exist_ok=True)

def _passport(note: str, meta: dict)->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="studio://drama")
    except Exception:
        pass

def _pause_wav(ms: int, path: str, sr: int=44100):
    n=int(sr*ms/1000.0)
    with wave.open(path,"w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        silence=struct.pack("<h",0)*n
        w.writeframes(silence)

def make(title: str, script: List[Dict[str,Any]], voices: Dict[str,Dict[str,Any]]|None=None, gap_ms: int=250)->Dict[str,Any]:
    """
    script: [{role, text}], voices: { role: {voice:"ru-RU-..."} }
    """
    _ensure()
    from modules.studio.tts import _speech, concat_wavs  # type: ignore
    ts=int(time.time()); slug=title.strip().replace(" ","_") or f"drama_{ts}"
    ddir=os.path.join(OUT, f"{slug}_{ts}")
    os.makedirs(ddir, exist_ok=True)

    parts=[]; srt=[]; t0_ms=0
    for idx, line in enumerate(script or []):
        role=str(line.get("role","")).strip() or "Unknown"
        text=str(line.get("text","")).strip()
        voice=(voices or {}).get(role,{}).get("voice") if isinstance(voices,dict) else None
        seg=os.path.join(ddir, f"seg_{idx:03d}.wav")
        _speech(f"{text}", voice, seg)
        # otsenka dlitelnosti segmenta
        with wave.open(seg,"rb") as r:
            nframes=r.getnframes(); sr=r.getframerate()
            dur_ms=int(1000*nframes/sr)
        t1_ms=t0_ms + dur_ms
        srt.append((idx+1, t0_ms, t1_ms, f"{role}: {text}"))
        parts.append(seg)
        # pauza
        if gap_ms>0:
            gap=os.path.join(ddir, f"gap_{idx:03d}.wav")
            _pause_wav(gap_ms, gap); parts.append(gap)
            t0_ms=t1_ms+gap_ms
        else:
            t0_ms=t1_ms

    wav=os.path.join(ddir, "drama.wav")
    ok=concat_wavs(parts, wav)
    mp3=None
    if ok and os.path.isfile(wav):
        # trying to make an MP3
        import subprocess, shutil
        if shutil.which(FFMPEG):
            mp3=wav.replace(".wav",".mp3")
            try:
                p=subprocess.run([FFMPEG,"-y","-i",wav,"-codec:a","libmp3lame","-q:a","2",mp3],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=21600)
                if p.returncode!=0 or not os.path.isfile(mp3): mp3=None
            except Exception:
                mp3=None

    # SRT
    def fmt(ms:int)->str:
        h=ms//3600000; ms%=3600000
        m=ms//60000; ms%=60000
        s=ms//1000; ms%=1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    srt_path=os.path.join(ddir,"drama.srt")
    with open(srt_path,"w",encoding="utf-8") as f:
        for no,a,b,txt in srt:
            f.write(f"{no}\n{fmt(a)} --> {fmt(b)}\n{txt}\n\n")

    meta={
        "title": title, "slug": slug, "dir": ddir,
        "wav": wav if ok else "",
        "mp3": mp3 or "",
        "items": len(script or []), "gap_ms": gap_ms
    }
    open(os.path.join(ddir,"metadata.json"),"w",encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=2))
    _passport("drama_make", meta)
    return {"ok": ok, "dir": ddir, "wav": meta["wav"], "mp3": meta["mp3"], "srt": srt_path, "items": meta["items"]}

def list_all()->Dict[str,Any]:
    _ensure()
    arr=[]
    for name in sorted(os.listdir(OUT)):
        d=os.path.join(OUT,name)
        if not os.path.isdir(d): continue
        m=os.path.join(d,"metadata.json")
        if os.path.isfile(m):
            import json
            try: arr.append(json.load(open(m,"r",encoding="utf-8")))
            except Exception: pass
    return {"ok": True, "items": arr}
# c=a+b



