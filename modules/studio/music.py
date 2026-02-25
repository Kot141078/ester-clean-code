# -*- coding: utf-8 -*-
"""modules/studio/music.py - prostaya generatsiya WAV (sintez tonami po gamme).

Mosty:
- Yavnyy: (Muzyka ↔ Video/Audio) daet fonovuyu dorozhku bez vneshnikh zavisimostey.
- Skrytyy #1: (Inzheneriya ↔ Signaly) chistye sinusy/ogibayuschie, normalizatsiya urovnya.
- Skrytyy #2: (Volya ↔ Flot) mozhno generirovat vo flite kak zadachu.

Zemnoy abzats:
Kak karmannyy sintezator: prostye noty i ritm - dostatochno dlya fona shortov.

# c=a+b"""
from __future__ import annotations
import os, wave, struct, math, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT=os.getenv("STUDIO_OUT","data/studio/out")

_SCALE = {
    "Cmaj":[0,2,4,5,7,9,11], "Amin":[0,2,3,5,7,8,10],
    "Gmaj":[0,2,4,5,7,9,11], "Emin":[0,2,3,5,7,8,10]
}

def _note_freq(semitone: int, base_a4: float=440.0)->float:
    return base_a4 * (2.0 ** ((semitone-57)/12.0))  # 57 = A4

def _seq(scale: str, length: int)->List[int]:
    base = _SCALE.get(scale, _SCALE["Amin"])
    out=[]
    p=45  # A2 ~ 110Hz
    import random
    for _ in range(length):
        out.append(p + random.choice(base) + random.choice([-12,0,12]))
    return out

def generate(seconds: int=10, bpm: int=100, scale: str="Amin", sample_rate: int=44100)->Dict[str,Any]:
    os.makedirs(OUT, exist_ok=True)
    beats = max(1, int(bpm * seconds / 60))
    notes = _seq(scale, beats)
    env_attack=0.01; env_release=0.08
    frames=[]
    for i, sem in enumerate(notes):
        freq=_note_freq(sem)
        dur = 60.0/bpm
        n   = int(dur*sample_rate)
        for k in range(n):
            t=k/sample_rate
            amp=1.0
            if t < env_attack: amp *= t/env_attack
            if t > dur - env_release: amp *= max(0.0, (dur-t)/env_release)
            val=math.sin(2*math.pi*freq*t)*0.35*amp
            frames.append(val)
    # normalize
    mx=max(1e-6, max(abs(x) for x in frames))
    frames=[int(32767*x/mx) for x in frames]
    fn=os.path.join(OUT, "music_last.wav")
    with wave.open(fn,"w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sample_rate)
        for v in frames:
            w.writeframes(struct.pack("<hh", v, v))
    return {"ok": True, "path": fn, "seconds": seconds, "bpm": bpm, "scale": scale}
# c=a+b