# -*- coding: utf-8 -*-
"""
modules/audio/drama.py — audio-drama po rolyam: razmetka, TTS-komanda, svedenie, SRT/VTT.

Mosty:
- Yavnyy: (TTS ↔ FFmpeg) gibkaya obvyazka pod lyubuyu lokalnuyu TTS-komandu.
- Skrytyy #1: (Passport ↔ Prozrachnost) vse sintezy/svedeniya fiksiruyutsya.
- Skrytyy #2: (Media/RAG ↔ Navigatsiya) teksty i taymingi mozhno klast v RAG.

Zemnoy abzats:
Eto kak radio-spektakl: roli, repliki, golosa. Nuzhna tolko TTS-komanda — ostalnoe sdelaem sami.

# c=a+b
"""
from __future__ import annotations
import os, re, json, time, subprocess, shlex
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE=os.getenv("CREATOR_DIR","data/creator")
FFMPEG=os.getenv("CREATOR_FFMPEG","ffmpeg")
TTS=os.getenv("TTS_CMD","").strip()

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "audio://drama")
    except Exception:
        pass

def prepare(script: str, cast: Dict[str,str])->Dict[str,Any]:
    """
    Parsit stroki vida 'ROL: tekst' → [{role, voice, text, i}]
    """
    lines=[]
    i=1
    for ln in script.splitlines():
        m=re.match(r"\\s*([^:]+)\\s*:\\s*(.+)", ln)
        if not m: continue
        role=m.group(1).strip(); text=m.group(2).strip()
        voice=cast.get(role,"default")
        lines.append({"i": i, "role": role, "voice": voice, "text": text})
        i+=1
    _passport("drama_prepare", {"lines": len(lines), "roles": len(set(x["role"] for x in lines))})
    return {"ok": True, "lines": lines}

def _tts_to(path_wav: str, text: str, voice: str)->bool:
    os.makedirs(os.path.dirname(path_wav), exist_ok=True)
    if TTS:
        # ozhidaem, chto komanda chitaet text iz stdin i pishet WAV v path_wav
        cmd=f"{TTS} --voice {shlex.quote(voice)} -o {shlex.quote(path_wav)}"
        try:
            p=subprocess.run(cmd, input=text.encode("utf-8"), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=21600)
            return p.returncode==0 and os.path.isfile(path_wav)
        except Exception:
            return False
    # zaglushka: 1.5s tishiny
    subprocess.run([FFMPEG,"-y","-f","lavfi","-i","anullsrc=r=48000:cl=mono","-t","1.5",path_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.isfile(path_wav)

def render(lines: List[Dict[str,Any]], out_dir: str)->Dict[str,Any]:
    os.makedirs(out_dir, exist_ok=True)
    parts=[]; t=0.0; srt=[]
    for k,ln in enumerate(lines, start=1):
        wav=os.path.join(out_dir, f"line_{k:03d}.wav")
        ok=_tts_to(wav, ln.get("text",""), ln.get("voice","default"))
        if not ok: return {"ok": False, "error": "tts_failed", "line": k}
        # grubaya otsenka dlitelnosti (prochitaem ashumer)
        dur=1.5
        parts.append(wav)
        # SRT
        t1=t; t2=t+dur; t=t2
        def _fmt(sec: float)->str:
            m=int(sec//60); s=sec-60*m; h=int(m//60); m=m%60; ms=int((s-int(s))*1000); return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"
        srt.append(f"{k}\\n{_fmt(t1)} --> {(_fmt(t2))}\\n{ln.get('role', '')}: {ln.get('text','')}\\n")
    # skleivaem
    concat=os.path.join(out_dir,"concat.txt")
    with open(concat,"w",encoding="utf-8") as f:
        for p in parts: f.write(f"file '{p}'\\n")
    out_wav=os.path.join(out_dir,"drama_mix.wav")
    subprocess.run([FFMPEG,"-y","-f","concat","-safe","0","-i",concat,"-c","copy",out_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    open(os.path.join(out_dir,"drama.srt"),"w",encoding="utf-8").write("\n".join(srt))
    _passport("drama_render", {"lines": len(lines), "out": out_wav})
    return {"ok": True, "out": out_wav, "srt": os.path.join(out_dir,"drama.srt")}
# c=a+b



