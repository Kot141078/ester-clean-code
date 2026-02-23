# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _read_text(path: str, max_bytes: int = 500_000) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _top_words(text: str, top_n: int = 10):
    words = re.findall(r"[A-Za-zA-Yaa-ya0-9_]{3,}", text.lower())
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return items[:top_n]


def analyze_skill(text: str | None = None, path: str | None = None) -> Dict[str, Any]:
    """
    Lokalnyy analiz teksta: razmery, plotnost, top-slova.
    """
    if path and not text:
        text = _read_text(path)

    if not text:
        return {"status": "error", "error": "text or path required"}

    lines = text.splitlines()
    words = re.findall(r"\S+", text)
    chars = len(text)
    top_words = _top_words(text, top_n=12)

    return {
        "status": "ok",
        "stats": {
            "chars": chars,
            "words": len(words),
            "lines": len(lines),
            "avg_line_len": int(chars / max(1, len(lines))),
        },
        "top_words": [{"word": w, "count": c} for w, c in top_words],
        "sample": "\n".join(lines[:5]),
    }