# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json

from modules.memory.core_sqlite import MemoryCore


def test_memory_core_write_and_search(tmp_path):
    core = MemoryCore(path=str(tmp_path / "core.sqlite"))
    try:
        rep = core.write_memory_add("fact", "Ivan likes tea and black coffee", {"source": "pytest"})
        assert rep["ok"] is True
        assert rep["event_id"]
        assert rep["memory_item_id"]

        rows = core.search("tea", limit=5)
        assert rows
        assert any("tea" in str(row.get("text") or "").lower() for row in rows)

        counts = core.status()["counts"]
        assert counts["events"] >= 1
        assert counts["memory_items"] >= 1
        assert counts["facts"] >= 1
    finally:
        core.close()


def test_memory_core_import_all_is_idempotent(tmp_path):
    snapshot = {
        "a": {
            "id": "fact-1",
            "type": "fact",
            "text": "Ivan prefers direct answers.",
            "meta": {"source": "snapshot"},
            "ts": 100,
            "vec": [0.1, 0.2],
        },
        "b": {
            "id": "sum-1",
            "type": "summary",
            "text": "Day summary about tea and plans.",
            "meta": {"source": "snapshot", "mode": "day"},
            "ts": 101,
        },
    }
    clean_memory = [{"ts": 200, "user": "Do you remember tea?", "assistant": "Yes, you like black tea."}]
    journal_rows = [{"ts": 300, "kind": "event", "source": "journal", "payload": {"text": "background task ok"}, "ok": True}]
    identity_dynamic = {
        "tone_profile": {"voice": "warm and direct"},
        "self_reflection": "Style can adapt while identity stays stable.",
        "recent_lessons": ["Keep answers concise."],
    }

    snapshot_path = tmp_path / "memory.json"
    clean_path = tmp_path / "clean_memory.jsonl"
    journal_path = tmp_path / "journal_events.jsonl"
    anchor_path = tmp_path / "anchor.txt"
    core_facts_path = tmp_path / "core_facts.txt"
    dynamic_path = tmp_path / "identity_dynamic.json"

    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    clean_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in clean_memory) + "\n", encoding="utf-8")
    journal_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in journal_rows) + "\n", encoding="utf-8")
    anchor_path.write_text("Ester is anchored to Ivan.", encoding="utf-8")
    core_facts_path.write_text("Ivan prefers direct answers.\nTea matters.\n", encoding="utf-8")
    dynamic_path.write_text(json.dumps(identity_dynamic, ensure_ascii=False), encoding="utf-8")

    core = MemoryCore(path=str(tmp_path / "core.sqlite"))
    try:
        rep1 = core.import_all(
            snapshot=snapshot_path,
            clean_memory=clean_path,
            journal=journal_path,
            anchor=anchor_path,
            core_facts=core_facts_path,
            identity_dynamic=dynamic_path,
        )
        counts1 = rep1["status"]["counts"]

        rep2 = core.import_all(
            snapshot=snapshot_path,
            clean_memory=clean_path,
            journal=journal_path,
            anchor=anchor_path,
            core_facts=core_facts_path,
            identity_dynamic=dynamic_path,
        )
        counts2 = rep2["status"]["counts"]

        for key in ("events", "memory_items", "facts", "identity_items", "episodes", "summaries"):
            assert counts2[key] == counts1[key]
    finally:
        core.close()


def test_facade_dual_write_and_cutover_query(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_MEMORY_CORE_PATH", str(tmp_path / "memory_core" / "ester_memory.sqlite"))
    monkeypatch.setenv("ESTER_MEMORY_CORE_ENABLED", "1")
    monkeypatch.setenv("ESTER_MEMORY_CORE_DUAL_WRITE", "1")
    monkeypatch.setenv("ESTER_MEMORY_CORE_READ_CUTOVER", "1")
    monkeypatch.setenv("ESTER_MEMORY_CORE_SHADOW_READ", "0")

    import modules.memory.core_sqlite as core_sqlite
    import modules.memory.store as store
    import modules.memory.facade as facade

    core_sqlite.reset_core_for_tests()
    importlib.reload(core_sqlite)
    importlib.reload(store)
    importlib.reload(facade)

    try:
        rec = facade.memory_add("fact", "Ivan trusts concise answers about tea.", {"source": "pytest"})
        assert isinstance(rec, dict)
        assert rec.get("id")

        counts = core_sqlite.get_core().counts()
        assert counts["events"] >= 1
        assert counts["memory_items"] >= 1

        rows = store.query("tea", top_k=5)
        assert rows
        assert any("tea" in str(row.get("text") or "").lower() for row in rows)
    finally:
        core_sqlite.reset_core_for_tests()
