# -*- coding: utf-8 -*-
"""modules/media/subs.py - parsing .srt/.vtt → spisok fragmentov i syroy tekst.

Mosty:
- Yavnyy: (Media ↔ Text) prevraschaem subtitry v udobnye kuski.
- Skrytyy #1: (KG ↔ Linker) mozhno kormit izvlechennyy tekst v KG.
- Skrytyy #2: (Memory ↔ Passport) gotovim tekst k upsert_with_passport.

Zemnoy abzats:
Berem subtitry - delaem iz nikh chitaemye abzatsy, chtoby mozgu bylo za chto zatsepitsya.

# c=a+b"""
from __future__ import annotations
import re, os
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TIME_RE = re.compile(r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})(?:[.,](?P<ms>\d{1,3}))?")

def _from_srt(text:str)->List[Dict[str,Any]]:
    blocks=re.split(r"\n\s*\n", text.strip(), flags=re.M)
    out=[]
    for b in blocks:
        lines=[l.strip() for l in b.splitlines() if l.strip()]
        if not lines: continue
        if "-->" in lines[0]:
            tline=lines[0]
            content=" ".join(lines[1:])
        else:
            if len(lines)>=2 and "-->" in lines[1]:
                tline=lines[1]; content=" ".join(lines[2:])
            else:
                continue
        ts=[x.strip() for x in tline.split("-->")]
        def to_sec(x:str)->float:
            m=TIME_RE.search(x or "")
            if not m: return 0.0
            h=int(m.group("h")); mi=int(m.group("m")); s=int(m.group("s")); ms=int(m.group("ms") or "0")
            return h*3600+mi*60+s+ms/1000.0
        out.append({"start": to_sec(ts[0]), "end": to_sec(ts[1]), "text": content})
    return out

def _from_vtt(text:str)->List[Dict[str,Any]]:
    # uproschennyy parser WebVTT
    lines=[l.rstrip() for l in text.splitlines()]
    cur=[]; buf=[]
    for ln in lines:
        if "-->" in ln:
            if buf: cur.append(buf); buf=[]
            buf=[ln]
        else:
            if buf is not None: buf.append(ln)
    if buf: cur.append(buf)
    out=[]
    for block in cur:
        tline=block[0]
        content=" ".join([x for x in block[1:] if x and not x.startswith("NOTE")])
        # timestamps like 00:00:03.500 --> 00:00:05.000
        ts=[x.strip() for x in tline.split("-->")]
        def to_sec_vtt(x:str)->float:
            m=TIME_RE.search(x or "")
            if not m: return 0.0
            h=int(m.group("h")); mi=int(m.group("m")); s=int(m.group("s")); ms=int(m.group("ms") or "0")
            return h*3600+mi*60+s+ms/1000.0
        out.append({"start": to_sec_vtt(ts[0]), "end": to_sec_vtt(ts[1]), "text": content})
    return out

def parse_subtitles(path:str)->Dict[str,Any]:
    p=os.path.abspath(path)
    data=open(p,"r",encoding="utf-8",errors="ignore").read()
    if p.lower().endswith(".srt"):
        frags=_from_srt(data)
    else:
        frags=_from_vtt(data)
    full_text=" ".join(x["text"] for x in frags)
    return {"ok": True, "fragments": frags, "text": full_text}
# c=a+b