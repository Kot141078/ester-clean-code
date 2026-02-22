# -*- coding: utf-8 -*-
"""Compatibility bridge for storage uploader implementation."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_IMPL_PATH = Path(__file__).resolve().parents[2] / "storage" / "uploader.py"
_SPEC = importlib.util.spec_from_file_location("ester_root_storage_uploader", str(_IMPL_PATH))
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot_load_storage_uploader:{_IMPL_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)  # type: ignore[union-attr]

test_target = _MODULE.test_target
upload_file = _MODULE.upload_file

__all__ = ["test_target", "upload_file"]
