# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import fnmatch
from typing import Dict, Any, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _read_text(path: str, max_bytes: int = 200_000) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _iter_files(root: str, pattern: Optional[str]) -> List[str]:
    out: List[str] = []
    for base, _, files in os.walk(root):
        for name in files:
            if pattern and not fnmatch.fnmatch(name, pattern):
                continue
            out.append(os.path.join(base, name))
    return out


def file_search_skill(query: str, root: str | None = None, pattern: str | None = None, max_results: int = 20) -> Dict[str, Any]:
    """Search teksta v faylakh.
    args:
      query: string dlya poiska
      root: direktoriya (po umolchaniyu cwd)
      pattern: glob dlya faylov (for example, *.py)
      max_results: maximum sovpadeniy"""
    q = (query or "").strip()
    if not q:
        return {"status": "error", "error": "query required"}

    base = root or os.getcwd()
    files = _iter_files(base, pattern)
    hits: List[Dict[str, Any]] = []

    for path in files:
        text = _read_text(path)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if q.lower() in line.lower():
                snippet = line.strip()
                hits.append({"path": path, "line": idx, "snippet": snippet})
                if len(hits) >= max_results:
                    return {"status": "ok", "count": len(hits), "results": hits}

    return {"status": "ok", "count": len(hits), "results": hits}