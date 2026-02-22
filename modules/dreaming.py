# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Legacy compatibility wrapper for historical import path:
    from modules.dreaming import DreamingEngine
"""

from typing import Any, Dict

from modules.dreams_engine import DreamRule, DreamsEngine


class DreamingEngine:
    """Backward-compatible adapter over canonical DreamsEngine."""

    def __init__(self, memory_manager: Any, provider: Any = None, seed: int | None = None, **kwargs: Any) -> None:
        self.memory_manager = memory_manager
        self.provider = provider
        self.seed = seed
        self.kwargs = dict(kwargs or {})
        self._engine = DreamsEngine(memory_manager, provider=provider, **self.kwargs)

    def run_for_user(self, user: str, k: int = 50) -> Dict[str, Any]:
        rule = DreamRule(query="*", k=int(k or 50))
        raw = self._engine.run([rule])

        clusters = raw.get("clusters") or []
        hypotheses = raw.get("hypotheses") or []
        if not isinstance(clusters, list):
            clusters = []
        if not isinstance(hypotheses, list):
            hypotheses = []

        # If structured memory is available, store a compact user-facing dream note.
        structured = getattr(self.memory_manager, "structured", None)
        add_record = getattr(structured, "add_record", None) if structured is not None else None
        if callable(add_record) and hypotheses:
            top = hypotheses[0]
            text = str(top.get("text") or "").strip()
            if text:
                try:
                    add_record(
                        text=f"[dream:{str(user or '').strip() or 'user'}] {text}",
                        tags=["dream"],
                        weight=0.7,
                    )
                except Exception:
                    pass

        return {
            "ok": bool(raw.get("ok")),
            "user": str(user or ""),
            "clusters": len(clusters),
            "hypotheses": len(hypotheses),
            "saved": int(raw.get("saved") or 0),
            "raw": raw,
        }


__all__ = ["DreamingEngine"]
