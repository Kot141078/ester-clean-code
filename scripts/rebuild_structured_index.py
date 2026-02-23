# -*- coding: utf-8 -*-
"""Repair and normalize structured memory index files."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Tuple


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _default_store_path() -> str:
    return os.path.join(_persist_dir(), "structured_mem", "store.json")


def _backup_path(base_path: str) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    root = os.path.dirname(os.path.abspath(base_path))
    return os.path.join(root, f"store_backup_{ts}.json")


def _normalize_records(records: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen_ids = set()
    for raw in records:
        if not isinstance(raw, dict):
            continue
        rec_id = str(raw.get("id") or "").strip()
        text = str(raw.get("text") or "").strip()
        if not rec_id or not text:
            continue
        if rec_id in seen_ids:
            continue
        seen_ids.add(rec_id)
        tags = raw.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        try:
            weight = float(raw.get("weight", 0.5))
        except Exception:
            weight = 0.5
        out.append(
            {
                "id": rec_id,
                "text": text,
                "tags": [str(t) for t in tags if str(t).strip()],
                "weight": weight,
                "mtime": int(raw.get("mtime") or 0),
            }
        )
    return out


def rebuild(path: str) -> str:
    """Normalize `records` and keep valid `alias_map`. Returns output path."""
    src_path = os.path.abspath(path)
    try:
        with open(src_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except UnicodeDecodeError:
        with open(src_path, "r", encoding="cp1251") as fh:
            data = json.load(fh)

    if isinstance(data, dict):
        records = list(data.get("records") or data.get("items") or [])
        alias_map = data.get("alias_map") or {}
    elif isinstance(data, list):
        records = list(data)
        alias_map = {}
    else:
        records = []
        alias_map = {}

    out = {
        "records": _normalize_records(records),
        "alias_map": dict(alias_map) if isinstance(alias_map, dict) else {},
    }

    backup = _backup_path(src_path)
    with open(backup, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    with open(src_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return src_path


def main() -> int:
    path = _default_store_path()
    if not os.path.exists(path):
        print("store.json not found - nothing to rebuild")
        return 0
    try:
        out = rebuild(path)
        print(f"Rebuilt structured index: {out}")
        return 0
    except Exception as exc:
        print(f"Failed to rebuild structured index: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
