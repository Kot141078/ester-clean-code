# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl_tail(path: str | Path, max_lines: int = 2000) -> List[Dict[str, Any]]:
    """Read recent JSON object records from a caller-provided JSONL file."""
    try:
        limit = int(max_lines)
    except Exception:
        limit = 2000
    if limit <= 0:
        return []

    try:
        p = Path(path)
    except Exception:
        return []
    if not p.is_file():
        return []

    rows: deque[Dict[str, Any]] = deque(maxlen=limit)
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []

    return list(rows)


__all__ = ["read_jsonl_tail"]
