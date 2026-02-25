# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _read_text(path: Path, max_bytes: int = 1_000_000) -> str:
    try:
        with path.open("rb") as f:
            data = f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def ingest_skill(
    text: str | None = None,
    path: str | None = None,
    glob: str = "**/*",
    tag: str = "local_docs",
) -> Dict[str, Any]:
    """Ingest text/file/directory into RAZH hub."""
    try:
        from modules.rag import hub  # type: ignore
    except Exception as e:
        return {"status": "error", "error": f"rag_hub_unavailable:{e}"}

    items: List[Dict[str, Any]] = []

    if text:
        items.append({"text": text, "meta": {"source": "skill_ingest"}})

    if path:
        p = Path(path)
        if p.is_file():
            items.append({"text": _read_text(p), "meta": {"path": str(p)}})
        elif p.is_dir():
            for fp in p.glob(glob):
                try:
                    if fp.is_file():
                        items.append({"text": _read_text(fp), "meta": {"path": str(fp)}})
                except Exception:
                    continue

    if not items:
        return {"status": "error", "error": "nothing_to_ingest"}

    res = hub.ingest_texts(items, tag=tag)  # type: ignore
    return {"status": "ok", "ingested": res}