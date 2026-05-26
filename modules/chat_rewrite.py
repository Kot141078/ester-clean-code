# -*- coding: utf-8 -*-
"""Deterministic text rewriter that preserves fenced code blocks."""

from __future__ import annotations

import re
from typing import List, Tuple

_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_PYTHON_START_RE = re.compile(
    r"^\s*(?:def\s+\w+\s*\(|class\s+\w+\s*(?:\(|:)|import\s+\w+|from\s+\w+|print\s*\(|[A-Za-z_]\w*\s*=)"
)
_PYTHON_CONT_RE = re.compile(r"^\s*(?:return\b|yield\b|raise\b|pass\b|break\b|continue\b|print\s*\()")
_SINGLE_ARG_DEF_RE = re.compile(r"^(\s*def\s+\w+\()\s*([A-Za-z_]\w*)\s*(\)\s*:.*)$")


def _normalize_text(text: str) -> str:
    out = text
    out = re.sub(r"[!]{2,}", "!", out)
    out = re.sub(r"[?]{2,}", "?", out)
    out = re.sub(r"\s+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def _looks_like_python_start(line: str) -> bool:
    return bool(_PYTHON_START_RE.match(line or ""))


def _looks_like_python_continuation(line: str) -> bool:
    if not line.strip():
        return True
    return line.startswith((" ", "\t")) or bool(_PYTHON_CONT_RE.match(line))


def _clean_python_block(block: str) -> str:
    lines = [line.rstrip() for line in str(block or "").splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""

    match = _SINGLE_ARG_DEF_RE.match(lines[0])
    if match:
        old_arg = match.group(2)
        if old_arg != "x":
            lines[0] = f"{match.group(1)}x{match.group(3)}"
            arg_re = re.compile(rf"\b{re.escape(old_arg)}\b")
            lines[1:] = [arg_re.sub("x", line) for line in lines[1:]]

    return "\n".join(lines)


def _stash_unfenced_python_blocks(text: str) -> Tuple[str, List[str]]:
    lines = str(text or "").splitlines()
    out: List[str] = []
    blocks: List[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if not _looks_like_python_start(line):
            out.append(line)
            idx += 1
            continue

        block_lines = [line]
        idx += 1
        while idx < len(lines) and _looks_like_python_continuation(lines[idx]):
            block_lines.append(lines[idx])
            idx += 1

        cleaned = _clean_python_block("\n".join(block_lines))
        if not cleaned:
            continue
        blocks.append(f"```python\n{cleaned}\n```")
        out.append(f"@@PYTHON_BLOCK_{len(blocks) - 1}@@")

    return "\n".join(out), blocks


def rewrite(text: str) -> str:
    """
    Rewrite prose part to a cleaner style while keeping fenced code blocks verbatim.
    """
    src = str(text or "")
    code_blocks: List[str] = []

    def _stash(match: re.Match[str]) -> str:
        code_blocks.append(match.group(0))
        return f"@@CODE_BLOCK_{len(code_blocks) - 1}@@"

    masked = _FENCE_RE.sub(_stash, src)
    masked, python_blocks = _stash_unfenced_python_blocks(masked)
    cleaned = _normalize_text(masked)

    for idx, block in enumerate(code_blocks):
        cleaned = cleaned.replace(f"@@CODE_BLOCK_{idx}@@", block)
    for idx, block in enumerate(python_blocks):
        cleaned = cleaned.replace(f"@@PYTHON_BLOCK_{idx}@@", block)

    return cleaned
