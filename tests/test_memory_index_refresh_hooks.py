from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_user_facts_refreshes_memory_index(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.memory_index as memory_index
    import modules.memory.user_facts_store as user_facts_store

    memory_index = importlib.reload(memory_index)
    user_facts_store = importlib.reload(user_facts_store)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе"])
    payload = json.loads(memory_index.overview_path().read_text(encoding="utf-8"))
    assert payload["schema"] == "ester.memory.overview.v1"
    assert payload["storage"]["users_total"] >= 1


def test_recent_docs_refreshes_memory_index(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.memory_index as memory_index
    import modules.memory.recent_docs as recent_docs

    memory_index = importlib.reload(memory_index)
    recent_docs = importlib.reload(recent_docs)

    recent_docs.remember_recent_doc(
        777,
        doc_id="doc-1",
        name="Посты.txt",
        summary="Recent summary for Посты.txt with the key post mentioned.",
        citations=["[Посты.txt | p. ?]"],
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
    )
    payload = json.loads(memory_index.overview_path().read_text(encoding="utf-8"))
    assert payload["storage"]["recent_doc_entries_total"] >= 1


def test_recall_diagnostics_refreshes_memory_index(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.active_context as active_context
    import modules.memory.memory_index as memory_index
    import modules.memory.profile_snapshot as profile_snapshot
    import modules.memory.recall_diagnostics as recall_diagnostics
    import modules.memory.user_facts_store as user_facts_store

    active_context = importlib.reload(active_context)
    memory_index = importlib.reload(memory_index)
    profile_snapshot = importlib.reload(profile_snapshot)
    recall_diagnostics = importlib.reload(recall_diagnostics)
    user_facts_store = importlib.reload(user_facts_store)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе"])
    snapshot = profile_snapshot.refresh_profile_snapshot("42", display_name="Test User", chat_id=777)
    bundle = active_context.build_active_memory_bundle(
        user_text="Что ты про меня помнишь?",
        evidence_memory="",
        user_facts=["Живёт в тестовом городе"],
        profile_context=profile_snapshot.render_profile_context(snapshot),
        honesty_block="[ACTIVE_MEMORY_HONESTY]\n- stance: stable\n- confidence: high",
    )
    recall_diagnostics.record_active_bundle(
        query="Что ты про меня помнишь?",
        user_id="42",
        chat_id="777",
        bundle=bundle,
        profile_snapshot=snapshot,
        provenance=[],
    )
    payload = json.loads(memory_index.overview_path().read_text(encoding="utf-8"))
    assert payload["latest"]["recall"]["state"] == "ready"
    assert payload["latest"]["recall"]["honesty_label"] == "stable"


def test_reply_trace_refreshes_memory_index(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.memory_index as memory_index
    import modules.memory.reply_trace as reply_trace

    memory_index = importlib.reload(memory_index)
    reply_trace = importlib.reload(reply_trace)

    reply_trace.record_reply_trace(
        query="Что ты помнишь про меня?",
        reply_text="Я помню, что ты живёшь в тестовом городе.",
        user_id="42",
        chat_id="777",
        reply_mode="fast_lane",
        provider="probe",
        trace={"stage_order": ["fast_final"], "stages": {"fast_final": {"present": True, "chars": 36}}},
        active_memory_bundle={"schema": "ester.active_memory.v1", "stats": {"has_honesty": True, "has_profile": True}},
        profile_snapshot={"summary": "Test User: Живёт в тестовом городе."},
        honesty_report={"label": "stable", "confidence": "high"},
        safe_history=[{"role": "user", "content": "Что ты помнишь про меня?"}],
    )
    payload = json.loads(memory_index.overview_path().read_text(encoding="utf-8"))
    assert payload["latest"]["reply_trace"]["state"] == "ready"
