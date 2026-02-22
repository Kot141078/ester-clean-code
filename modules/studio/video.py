# -*- coding: utf-8 -*-
"""
modules/studio/video.py — sborka video iz subtitrov/fonovogo audio i kartinok (FFmpeg).

Mosty:
- Yavnyy: (Tekst/Audio ↔ Video) sozdaet roliki dlya short/long formatov s taymingom.
- Skrytyy #1: (Inzheneriya ↔ Parametry) pravilno stavit fps, razmer kadra, kodek, bitreyt.
- Skrytyy #2: (Garazh/Flot ↔ Volya) mozhet ispolnyatsya kak zadacha.

Zemnoy abzats:
Eto «skleyschik»: titry+fon → akkuratnyy mp4 pod nuzhnoe sootnoshenie storon.

# c=a+b
"""
from __future__ import annotations
import os, json, time, subprocess, tempfile
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT=os.getenv("STUDIO_OUT","data/studio/out")
TMP=os.getenv("STUDIO_TMP","data/studio/tmp")
FFMPEG=os.getenv("FFMPEG_BIN","ffmpeg")

def _ensure():
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)

def _subs_to_ass(subs: List[Dict[str,Any]], ass_path: str, w: int, h: int):
    hdr=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: txt,Arial,36,&H00FFFFFF,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,0

[Events]
Format: Layer, Start, End, Style, Text
"""
    def ts(x: float)->str:
        h=int(x//3600); m=int((x%3600)//60); s=(x%60)
        return f"{h:d}:{m:02d}:{s:05.2f}".replace(".",",")
    lines=[hdr]
    for it in subs or []:
        lines.append(f"Dialogue: 0,{ts(it.get('t0',0))},{ts(it.get('t1',0))},txt,{it.get('text','').replace(',', ';')}")
    open(ass_path,"w",encoding="utf-8").write("\n".join(lines))

def render(title: str, mode: str="short", aspect: str="9:16", duration: float|None=None, text_subs: List[Dict[str,Any]]|None=None, bgm: str|None=None, fps: int=30)->Dict[str,Any]:
    _ensure()
    if aspect=="9:16": size=(1080,1920)
    else: size=(1920,1080)
    w,h=size
    # fon — chernyy
    dur= duration or (text_subs[-1]["t1"] if text_subs else 10.0)
    out=os.path.join(OUT, f"{title.replace(' ','_')}_{aspect.replace(':','x')}.mp4")
    ass=os.path.join(TMP, "subs.ass"); _subs_to_ass(text_subs or [], ass, w, h)
    cmd=[FFMPEG, "-y",
         "-f","lavfi","-i", f"color=c=black:s={w}x{h}:d={dur}",
         "-r", str(fps)]
    if bgm:
        cmd += ["-i", bgm]
    cmd += ["-vf", f"ass={ass}", "-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p","-movflags","+faststart"]
    if bgm:
        cmd += ["-c:a","aac","-shortest"]
    else:
        cmd += ["-an"]
    cmd += [out]
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(20, int(dur*4)))
        ok=(p.returncode==0)
    except Exception:
        ok=False
    return {"ok": ok, "path": out, "seconds": dur, "fps": fps, "aspect": aspect}
# c=a+b