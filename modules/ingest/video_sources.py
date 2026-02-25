# -*- coding: utf-8 -*-
"""modules/ingest/video_sources.py - istochniki video: URL (yt-dlp) i lokalnye fayly. Subtitle, metadata, audio track.

Mosty:
- Yavnyy: (Infoteoriya ↔ Seti) yt-dlp/ffprobe dayut szhatoe opisanie istochnika (tegi/taymingi) dlya posleduyuschey semantiki.
- Skrytyy #1: (Kibernetika ↔ Resurs-menedzhment) Adapter vybiraet strategy skachivaniya (audio-only vs full) po resursam.
- Skrytyy #2: (Bayes ↔ Deduplikatsiya) Kheshi faylov sluzhat nablyudeniyami dlya “to zhe li eto video” - umenshaem povtornuyu rabotu.

Zemnoy abzats:
Eto “logist” konveyera: reshaet, where brat syre (fayl/URL), v kakom vide (tolko zvuk/polnoe video), kak soprovodit nakladnoy (metadannye/subtitry).

# c=a+b"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .video_common import ProbeResult, ensure_dir, ffprobe, sha256_file, _safe_run
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@dataclass
class SourceArtifacts:
    workdir: str
    local_path: str
    meta_json: Optional[str]
    subs_paths: List[str]
    audio_path: Optional[str]

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def fetch_from_url(url: str, prefer_audio: bool = True, want_subs: bool = True) -> SourceArtifacts:
    """Skachivaet URL (YouTube/drugie) cherez yt-dlp (esli net - brosaet RuntimeError).
    Vozvraschaet put k faylu (audio or video), JSON metadannykh i puti subtitrov (esli byli)."""
    if not _have("yt-dlp"):
        raise RuntimeError("yt-dlp not found in PATH")

    workdir = tempfile.mkdtemp(prefix="ester_video_")
    outtmpl = os.path.join(workdir, "%(id)s.%(ext)s")

    base = ["yt-dlp", "--no-progress", "-o", outtmpl, "-J", "--write-description"]
    if want_subs:
        base += ["--write-sub", "--write-auto-sub", "--convert-subs", "srt"]
    if prefer_audio:
        base += ["-x", "--audio-format", "m4a"]

    # Poluchim meta JSON
    code, out, err = _safe_run(["yt-dlp", "-J", url], timeout=21600.0)
    meta_path = None
    if code == 0 and out.strip():
        meta_path = os.path.join(workdir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(out)

    code, _, err = _safe_run(base + [url], timeout=1800.0)
    if code != 0:
        raise RuntimeError(f"yt-dlp failed: {err.strip()}")

    # Naydem osnovnoy fayl
    candidates = list(Path(workdir).glob("*.*"))
    main_file = None
    for p in candidates:
        if p.suffix.lower() in (".m4a", ".mp3") and prefer_audio:
            main_file = str(p); break
    if not main_file:
        # vyberem samyy «tyazhelyy»
        main_file = str(max(candidates, key=lambda p: p.stat().st_size))

    subs = [str(p) for p in Path(workdir).glob("*.srt")]
    # If you downloaded the video, let’s try to rip out the audio separately (could be mpch/webm)
    audio_path = main_file if main_file.lower().endswith((".m4a", ".mp3")) else None
    return SourceArtifacts(workdir, main_file, meta_path, subs, audio_path)

def fetch_from_path(path: str) -> SourceArtifacts:
    """Adapter for local files: checks availability, tries to pull out srt via ffmpeg, audio path for now None."""
    if not os.path.isfile(path):
        raise RuntimeError(f"file-not-found: {path}")
    workdir = tempfile.mkdtemp(prefix="ester_video_")
    # Let's copy it to the working folder (to store side effects there)
    local = os.path.join(workdir, os.path.basename(path))
    shutil.copyfile(path, local)
    # Subtitles from the container (if available)
    subs = []
    try:
        subs = [* (p for p in _extract_subs(local, workdir))]
    except Exception:
        subs = []
    return SourceArtifacts(workdir, local, None, subs, None)

def _extract_subs(local_path: str, workdir: str) -> List[str]:
    out = ensure_dir(os.path.join(workdir, "subs"))
# return [* (p for p in extract_subs_ffmpeg(local_path, out))]  # type: ignore[name-defined]




