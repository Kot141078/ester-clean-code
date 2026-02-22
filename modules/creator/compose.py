# -*- coding: utf-8 -*-
"""
modules/creator/compose.py — sborka video iz kartinok i (opts.) audio, cherez ffmpeg.

Mosty:
- Yavnyy: (FS ↔ Media) prevraschaem massiv izobrazheniy v mp4.
- Skrytyy #1: (Passport ↔ Prozrachnost) logiruem sborki, puti i dlitelnost.
- Skrytyy #2: (Uploader ↔ Metadannye) na vykhode fayl gotov k publikatsii.

Zemnoy abzats:
Kak montazhnyy pult: kinul kartinki — poluchil rolik. Khotite — podlozhim dorozhku.

# c=a+b
"""
from __future__ import annotations
import os, glob, subprocess, shlex, time
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE=os.getenv("CREATOR_DIR","data/creator")
FFMPEG=os.getenv("CREATOR_FFMPEG","ffmpeg")
FPS=int(os.getenv("CREATOR_IMAGE_FPS","1") or "1")

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "creator://compose")
    except Exception:
        pass

def _collect_images(paths: List[str])->List[str]:
    imgs=[]
    for p in paths or []:
        if os.path.isdir(p):
            for ext in ("*.jpg","*.jpeg","*.png","*.bmp","*.webp"):
                imgs+=sorted(glob.glob(os.path.join(p, ext)))
        elif os.path.isfile(p):
            imgs.append(p)
    # normalizuem prostranstva
    out=[]
    for i,src in enumerate(imgs):
        dst=os.path.join(BASE,"tmp",f"img_{i:04d}.png")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if src.lower().endswith(".png"): 
            # prosto skopiruem
            open(dst,"wb").write(open(src,"rb").read())
        else:
            # konversiya cherez ffmpeg
            subprocess.run([FFMPEG,"-y","-i",src,dst], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out.append(dst)
    return out

def compose(images: List[str], out_path: str, audio: str|None=None)->Dict[str,Any]:
    if not images: return {"ok": False, "error":"no_images"}
    frames=_collect_images(images)
    list_txt=os.path.join(BASE,"tmp","list.txt")
    with open(list_txt,"w",encoding="utf-8") as f:
        for p in frames: f.write(f"file '{p}'\\n")
        # dlitelnost odnogo kadra = 1/FPS
    # delaem slaydshou
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cmd=[FFMPEG,"-y","-r",str(FPS),"-f","concat","-safe","0","-i",list_txt,"-vf","format=yuv420p","-pix_fmt","yuv420p","-movflags","+faststart","-an",out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if audio and os.path.isfile(audio):
        # miks audio
        out2=out_path.rsplit(".",1)[0]+"_a.mp4"
        subprocess.run([FFMPEG,"-y","-i",out_path,"-i",audio,"-c:v","copy","-c:a","aac","-shortest",out2], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out_path=out2
    _passport("creator_compose", {"images": len(frames), "out": out_path})
    return {"ok": True, "out": out_path}
# c=a+b