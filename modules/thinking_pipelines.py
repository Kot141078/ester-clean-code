# -*- coding: utf-8 -*-
"""
modules.thinking_pipelines — lightweight helper for file-based thinking workflows.

This module exists so that legacy imports like `from modules.thinking_pipelines import run_from_file`
work again by simply reading a YAML/JSON spec and returning the declared actions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None


def _load_spec(path: str) -> Dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    loader = None
    if YAML is not None:
        loader = YAML(typ="safe")
        spec = loader.load(raw)
    else:
        import yaml  # type: ignore[import]

        spec = yaml.safe_load(raw)
    if not isinstance(spec, dict):
        return {}
    return spec or {}


def _normalize_actions(value: Optional[Any]) -> List[Dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def run_from_file(path: str) -> Dict[str, Any]:
    """
    Load a rule spec from YAML/JSON and return its actions plus diagnostics.
    """
    try:
        spec = _load_spec(path)
    except Exception as exc:  # pragma: no cover - parsing errors should be visible
        return {"ok": False, "error": str(exc)}
    actions = _normalize_actions(spec.get("actions"))
    return {
        "ok": True,
        "actions": actions,
        "flashback": spec.get("flashback") or {},
        "spec": spec,
    }


__all__ = ["run_from_file"]
