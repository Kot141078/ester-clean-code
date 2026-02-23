# -*- coding: utf-8 -*-
"""
tests/docs/test_generate_openapi_script.py — smoke generatora OpenAPI.
"""
from __future__ import annotations

import os

import yaml  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import scripts.generate_openapi_from_routes as gen  # type: ignore
    from app import app as flask_app  # type: ignore
except Exception:  # pragma: no cover
    gen = None
    flask_app = None  # type: ignore


def test_build_spec_paths_present():
    assert gen is not None and flask_app is not None, "imports failed"
    spec = gen.build_spec()
    assert "openapi" in spec
    assert "paths" in spec
    # khotya by odin put
    assert len(spec["paths"]) >= 1

    # Dopolnitelno proverim, chto safe_dump ne padaet
    text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)
# assert "openapi:" in text