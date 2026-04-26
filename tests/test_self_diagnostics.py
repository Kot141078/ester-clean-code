from __future__ import annotations

import importlib


def test_self_diagnostics_reads_recall_and_reply_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.active_context as active_context
    import modules.memory.profile_snapshot as profile_snapshot
    import modules.memory.recall_diagnostics as recall_diagnostics
    import modules.memory.reply_trace as reply_trace
    import modules.memory.self_diagnostics as self_diagnostics
    import modules.memory.user_facts_store as user_facts_store

    active_context = importlib.reload(active_context)
    profile_snapshot = importlib.reload(profile_snapshot)
    recall_diagnostics = importlib.reload(recall_diagnostics)
    reply_trace = importlib.reload(reply_trace)
    self_diagnostics = importlib.reload(self_diagnostics)
    user_facts_store = importlib.reload(user_facts_store)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе"])
    snapshot = profile_snapshot.refresh_profile_snapshot("42", display_name="Test User", chat_id=777)
    bundle = active_context.build_active_memory_bundle(
        user_text="Что ты помнишь про меня?",
        evidence_memory="В профиле есть факт про тестовый город.",
        user_facts=["Живёт в тестовом городе"],
        profile_context=profile_snapshot.render_profile_context(snapshot),
        honesty_block="[ACTIVE_MEMORY_HONESTY]\n- stance: stable\n- confidence: high",
    )
    recall_diagnostics.record_active_bundle(
        query="Что ты помнишь про меня?",
        user_id="42",
        chat_id="777",
        bundle=bundle,
        profile_snapshot=snapshot,
        provenance=[{"doc_id": "doc-1", "path": str(tmp_path / 'doc.txt'), "page": 1}],
    )
    reply_trace.record_reply_trace(
        query="Что ты помнишь про меня?",
        reply_text="Я помню, что ты живёшь в тестовом городе.",
        user_id="42",
        chat_id="777",
        reply_mode="cascade",
        provider="probe",
        trace={"stage_order": ["brief", "draft"], "stages": {"brief": {"present": True, "chars": 100}, "draft": {"present": True, "chars": 140}}},
        active_memory_bundle=bundle,
        profile_snapshot=snapshot,
        honesty_report={"label": "stable", "confidence": "high", "provenance_count": 1},
        provenance=[{"doc_id": "doc-1", "path": str(tmp_path / 'doc.txt'), "page": 1}],
        safe_history=[{"role": "user", "content": "Что ты помнишь про меня?"}],
    )

    report = self_diagnostics.ensure_materialized()
    assert report["status_label"] in {"instrumented", "partial"}
    assert report["trace_mode"] == "cascade"
    assert report["trace_coverage_label"] in {"low", "moderate", "high"}
