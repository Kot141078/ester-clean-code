# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.memory.memory_bus import MemoryBus


def test_memory_bus_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("PYTHONPYCACHEPREFIX", str(tmp_path / "pycache"))
    monkeypatch.setenv("CHROMA_UI_NO_EMBED", "1")
    monkeypatch.setenv("CHROMA_UI_SCAN", "0")
    monkeypatch.setenv("CHROMA_AUTO_HEAL_ENV", "0")

    bus = MemoryBus(persist_dir=str(tmp_path), use_vector=True, use_chroma=True)
    bus.add_record("OCR pipeline stores PDF invoice text.", kind="fact", tags=["ocr", "pdf"])
    bus.add_record("Flashback should find OCR memory offline.", kind="fact", tags=["ocr"])

    hits = bus.flashback("ocr", k=5)
    assert hits
    assert any("ocr" in str(h.get("text") or "").lower() for h in hits)

    bus.close()
