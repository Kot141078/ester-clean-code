# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import sys


def test_legacy_memory_module_supports_source_submodules(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path / "persist"))
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}

    for name in ["memory.decay_gc", "memory.kg_store", "memory"]:
        sys.modules.pop(name, None)

    memory = importlib.import_module("memory")
    assert hasattr(memory, "HumanMemory")
    assert hasattr(memory, "memory_add")
    assert getattr(memory, "__path__", None)

    decay_gc = importlib.import_module("memory.decay_gc")
    kg_store = importlib.import_module("memory.kg_store")
    assert hasattr(decay_gc, "DecayGC")
    assert hasattr(decay_gc, "DecayRules")
    assert hasattr(kg_store, "KGStore")

    after = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    assert after == before
