# -*- coding: utf-8 -*-
"""Deterministic text rewriter that preserves fenced code blocks."""
from __future__ import annotations

import re
from typing import List


_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _normalize_text(text: str) -> str:
    out = text
    out = re.sub(r"[!]{2,}", "!", out)
    out = re.sub(r"[?]{2,}", "?", out)
    out = re.sub(r"\s+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def rewrite(text: str) -> str:
    """
    Rewrite prose part to a cleaner style while keeping fenced code blocks verbatim.
    """
    src = str(text or "")
    code_blocks: List[str] = []

    def _stash(match: re.Match[str]) -> str:
        code_blocks.append(match.group(0))
        return f"@@CODE_BLOCK_{len(code_blocks)-1}@@"

    masked = _FENCE_RE.sub(_stash, src)
    cleaned = _normalize_text(masked)

    for idx, block in enumerate(code_blocks):
        cleaned = cleaned.replace(f"@@CODE_BLOCK_{idx}@@", block)

    return cleaned
