# -*- coding: utf-8 -*-
"""modules/social/subs.py - konvertatsiya subtitrov ASS → SRT.

Mosty:
- Yavnyy: (Tekst ↔ Formaty) vydaem SRT, sovmestimyy s YouTube/TikTok.
- Skrytyy #1: (Studiya ↔ Video) berem ASS, chto uzhe generiruet studiya.
- Skrytyy #2: (Garazh ↔ Sotskit) oblegchaet sborku upload-kit bez vneshnikh instrumentov.

Zemnoy abzats:
Kak perepisat titry s odnoy bumazhki na druguyu formu - no akkuratno po millisekundam.

# c=a+b"""
from __future__ import annotations
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def ass_to_srt(ass_text: str)->str:
    # A very simple parsing of the lines "Dialog: 0,0:00:01.00,0:00:03.50,Style,Text..."
    out=[]
    idx=1
    for line in ass_text.splitlines():
        if not line.startswith("Dialogue:"): continue
        parts=line.split(",", 9)
        if len(parts)<10: continue
        t0=parts[1].strip().replace(".",",")
        t1=parts[2].strip().replace(".",",")
        text=parts[9].strip()
        text=re.sub(r"\{.*?\}","",text)  # ubrat tegi
        text=text.replace("\\N","\n")
        out.append(f"{idx}\n{t0} --> {t1}\n{text}\n")
        idx+=1
    return "\n".join(out).strip()+"\n"
# c=a+b