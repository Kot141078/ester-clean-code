# -*- coding: utf-8 -*-
"""
modules/video/metadata/ffprobe_ex.py — rasshirennyy ffprobe-adapter (lokalnye fayly i udalennye URL po best-effort).

Funktsii:
  • probe(source: dict) -> dict  # source: {"url": "..."} ili {"path": "..."}
  • sys_capabilities() -> dict   # nalichie binarey/moduley (ffmpeg/ffprobe/yt-dlp/whisper)
  • safe_head(url: str, timeout=4.0) -> dict  # proverka dostupnosti URL bez skachivaniya

Mosty:
- Yavnyy: (Inzheneriya ↔ Memory) normalizovannye metadannye dlya pamyati i posleduyuschey vektorizatsii.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) probe ne tyanet krupnye bayty, snizhaya riski i nagruzku.
- Skrytyy #2: (Kibernetika ↔ Kontrol) sys_capabilities daet RuleHub ponyatnye rychagi (kogda vklyuchat rezhim B).

Zemnoy abzats:
Eto «schup» i «profilea» na video: proveryaem, chto dostupno, i izvlekaem profile (format/dlina/dorozhki) bez tyazheloy zagruzki.

# c=a+b
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
YTDLP = os.getenv("YTDLP_BIN", "yt-dlp")

def _run(cmd: list[str], timeout: float = 6.0) -> tuple[int, str, str]:
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        return p.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")
    except Exception as e:
        return -1, "", str(e)

def sys_capabilities() -> Dict[str, Any]:
    def has(bin_name: str) -> bool:
        code, out, err = _run([bin_name, "-version"], timeout=2.0)
        return code == 0
    caps = {
        "ffprobe": has(FFPROBE),
        "ffmpeg": has(FFMPEG),
        "yt_dlp": False,
        "python_whisper": False,
        "python_faster_whisper": False
    }
    # yt-dlp: libo binar, libo modul
    if has(YTDLP):
        caps["yt_dlp"] = True
    else:
        try:
            import yt_dlp  # type: ignore
            caps["yt_dlp"] = True  # modul ustanovlen
        except Exception:
            pass
    try:
        import whisper  # type: ignore
        caps["python_whisper"] = True  # noqa
    except Exception:
        pass
    try:
        import faster_whisper  # type: ignore
        caps["python_faster_whisper"] = True  # noqa
    except Exception:
        pass
    return caps

def safe_head(url: str, timeout: float = 4.0) -> Dict[str, Any]:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.getcode(), "ct": r.headers.get("Content-Type", ""), "cl": r.headers.get("Content-Length")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def probe(source: Dict[str, Any]) -> Dict[str, Any]:
    path = (source.get("path") or "").strip()
    url = (source.get("url") or "").strip()
    if not path and not url:
        return {"ok": False, "error": "path or url required"}
    if url:
        # probuem ffprobe po seti (nekotorye sborki umeyut), inache head
        code, out, err = _run([FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", url], timeout=6.0)
        if code == 0 and out.strip():
            try:
                j = json.loads(out)
                j["ok"] = True
                j["source"] = {"url": url}
                return j
            except Exception:
                pass
        head = safe_head(url)
        return {"ok": head.get("ok", False), "source": {"url": url}, "head": head}
    # lokalnyy fayl
    if not os.path.isfile(path):
        return {"ok": False, "error": f"no such file: {path}"}
    code, out, err = _run([FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path], timeout=6.0)
    if code == 0 and out.strip():
        try:
            j = json.loads(out)
            j["ok"] = True
            j["source"] = {"path": path}
            return j
        except Exception as e:
            return {"ok": False, "error": str(e)}
# return {"ok": False, "error": err or "ffprobe failed"}