# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_persist_dir(persist_dir: Optional[str]) -> Path:
    base = str(persist_dir or os.getenv("PERSIST_DIR") or "").strip()
    if not base:
        base = str((Path.cwd() / "data").resolve())
    out = Path(base).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


class DreamStore:
    def __init__(self, persist_dir: Optional[str] = None) -> None:
        self.persist_dir = _resolve_persist_dir(persist_dir)
        self.path = (self.persist_dir / "dreams" / "dreams.jsonl").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def tail(self, limit: int = 20) -> List[Dict[str, Any]]:
        top_k = max(1, int(limit or 20))
        if not self.path.exists() or not self.path.is_file():
            return []
        lines: List[str] = []
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return []

        out: List[Dict[str, Any]] = []
        for line in lines[-top_k:]:
            s = line.strip()
            if not s:
                continue
            try:
                item = json.loads(s)
            except Exception:
                continue
            if isinstance(item, dict):
                out.append(item)
        return out

    def count(self) -> int:
        if not self.path.exists() or not self.path.is_file():
            return 0
        n = 0
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        n += 1
        except Exception:
            return 0
        return n

    def status(self) -> Dict[str, Any]:
        tail = self.tail(limit=1)
        return {
            "path": str(self.path),
            "count": self.count(),
            "last": tail[0] if tail else None,
        }
