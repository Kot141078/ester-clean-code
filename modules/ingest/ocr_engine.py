# -*- coding: utf-8 -*-
"""
OCR engine (tesseract CLI, stdlib-only integration).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, Iterable, Optional

from modules.ingest.common import persist_dir


_SUPPORTED_MIME = {"image/png", "image/jpeg", "image/bmp", "image/tiff"}


def _guess_mime(name: str, data: bytes) -> str:
    low = str(name or "").lower()
    if low.endswith(".png"):
        return "image/png"
    if low.endswith(".jpg") or low.endswith(".jpeg"):
        return "image/jpeg"
    if low.endswith(".bmp"):
        return "image/bmp"
    if low.endswith(".tif") or low.endswith(".tiff"):
        return "image/tiff"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "application/octet-stream"


def _safe_stem(name: str) -> str:
    base = os.path.basename(str(name or "ocr_input"))
    stem, _ext = os.path.splitext(base)
    stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)
    return stem or "ocr_input"


def _find_tesseract() -> Optional[str]:
    override = os.getenv("TESSERACT_EXE", "").strip()
    if override:
        return override if os.path.isfile(override) else None
    return shutil.which("tesseract")


def run_ocr(name: str, data: bytes, lang: str = "eng", tags: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    mime = _guess_mime(name, data)
    root = os.path.join(persist_dir(), "ingest", "ocr")
    os.makedirs(root, exist_ok=True)
    ts = int(time.time())
    out_path = os.path.join(root, f"{_safe_stem(name)}_{ts}.txt")

    if mime not in _SUPPORTED_MIME:
        raise RuntimeError(f"OCR ne podderzhivaet MIME: {mime}")

    exe = _find_tesseract()
    if not exe:
        raise RuntimeError("OCR engine unavailable: tesseract executable not found.")

    suffix = os.path.splitext(str(name or ""))[1] or ".bin"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        cp = subprocess.run(
            [exe, tmp_path, "stdout", "-l", str(lang or "eng")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if cp.returncode != 0:
            err = (cp.stderr or cp.stdout or "").strip()[:2000]
            raise RuntimeError(f"OCR tesseract failed: {err}")
        text = (cp.stdout or "").strip()
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        return {
            "ok": True,
            "text": text,
            "path": out_path,
            "mime": mime,
            "engine": "tesseract",
            "tags": list(tags or []),
        }
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
