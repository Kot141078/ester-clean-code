# -*- coding: utf-8 -*-
"""modules/video/subtitles/normalize.py - sbor/konversiya/normalizatsiya subtitrov (srt/vtt/ass) + fallback ASR.

Funktsii:
  • load_and_normalize(path_or_text: str, fmt_hint: str|None, lang_hint: str|None) -> dict
  • from_vtt_text(vtt: str) -> dict # universalnyy plain-tekst + uproschennaya razmetka taymkodov
  • try_asr(audio_path: str, model_hint='base') -> dict # whisper/faster_whisper esli est

Mosty:
- Yavnyy: (Memory ↔ Inzheneriya) privodim subtitry k edinomu “prostomu” vidu dlya indeksirovaniya.
- Skrytyy #1: (Infoteoriya ↔ Masshtab) ogranichivaem razmer i obedinyaem fragmenty, snizhaya noise.
- Skrytyy #2: (Kibernetika ↔ Nadezhnost) fallback ASR vklyuchaetsya tolko pri dostupnosti modeley/binarey.

Zemnoy abzats:
This is “perepakovschik teksta”: kakuyu kapsulu ni prinesut (vtt/srt/ass) - na vykhode akkuratnyy plain-text dlya uma i pamyati.

# c=a+b"""
from __future__ import annotations

import os
import re
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SUBS_MAX = int(os.getenv("SUBS_MAX_BYTES", "2000000"))

def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    return s

def from_vtt_text(vtt: str) -> Dict[str, Any]:
    lines = []
    blocks = re.split(r"\n\n+", vtt.strip(), flags=re.M)
    for b in blocks:
        # uberem WEBVTT header i pozitsii
        if b.strip().upper().startswith("WEBVTT"):
            continue
        # timecodes → [hh:mm:ss.mmm --> ...]
        t = re.findall(r"(\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3})", b)
        text = _strip_tags(re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", "", b)).strip()
        if not text:
            continue
        lines.append(("[[{}]] ".format(t[0]) if t else "") + text.replace("\n", " ").strip())
    return {"ok": True, "text": "\n".join(lines)}

def load_and_normalize(path_or_text: str, fmt_hint: str | None = None, lang_hint: str | None = None) -> Dict[str, Any]:
    # if this is the path to the file, we read it, otherwise we take it as text
    if os.path.isfile(path_or_text):
        if os.path.getsize(path_or_text) > SUBS_MAX:
            return {"ok": False, "error": "subtitle too large"}
        txt = open(path_or_text, "r", encoding="utf-8", errors="ignore").read()
    else:
        txt = path_or_text
    # auto-detect very roughly
    txt_head = txt[:200].strip().upper()
    if (fmt_hint or "").lower() == "vtt" or "WEBVTT" in txt_head:
        return from_vtt_text(txt)
    # srt: taymkody vida 00:00:12,345 --> 00:00:14,567
    if (fmt_hint or "").lower() == "srt" or re.search(r"\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}", txt):
        norm = re.sub(r"\r", "", txt)
        norm = re.sub(r"^\d+\s*$", "", norm, flags=re.M)  # nomera blokov
        norm = _strip_tags(norm)
        norm = re.sub(r"\n{3,}", "\n\n", norm)
        return {"ok": True, "text": norm.strip()}
    # ACC/SSA: extract a simple string
    if "[Script Info]" in txt_head or "[V4+" in txt_head:
        lines = []
        for line in txt.splitlines():
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) >= 10:
                    lines.append(_strip_tags(parts[-1]))
        return {"ok": True, "text": "\n".join(lines)}
    # plain text fallback
    return {"ok": True, "text": _strip_tags(txt).strip()}

def try_asr(audio_path: str, model_hint: str = "base") -> Dict[str, Any]:
    # Poprobuem faster_whisper → whisper; inache — no-op
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model = WhisperModel(model_hint)
        segments, info = model.transcribe(audio_path)
        out = []
        for seg in segments:
            out.append(f"[[{seg.start:.2f}-{seg.end:.2f}]] {seg.text.strip()}")
        return {"ok": True, "text": "\n".join(out), "engine": "faster_whisper"}
    except Exception:
        pass
    try:
        import whisper  # type: ignore
        model = whisper.load_model(model_hint)
        res = model.transcribe(audio_path)
        return {"ok": True, "text": res.get("text", "").strip(), "engine": "whisper"}
    except Exception:
        pass
    # return {"ok": False, "error": "no asr engine"}
