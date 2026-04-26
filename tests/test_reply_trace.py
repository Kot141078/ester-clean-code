from __future__ import annotations

import importlib
import json


def test_reply_trace_persists_and_materializes_sidecars(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.internal_trace_companion as internal_trace_companion
    import modules.memory.internal_trace_coverage as internal_trace_coverage
    import modules.memory.reply_trace as reply_trace
    import modules.memory.self_diagnostics as self_diagnostics

    internal_trace_companion = importlib.reload(internal_trace_companion)
    internal_trace_coverage = importlib.reload(internal_trace_coverage)
    reply_trace = importlib.reload(reply_trace)
    self_diagnostics = importlib.reload(self_diagnostics)

    result = reply_trace.record_reply_trace(
        query="Что ты помнишь про меня?",
        reply_text="Я помню, что ты живёшь в тестовом городе.",
        user_id="42",
        chat_id="777",
        reply_mode="cascade",
        provider="probe",
        trace={
            "stage_order": ["brief", "draft", "critic", "final"],
            "stages": {
                "brief": {"present": True, "chars": 100},
                "draft": {"present": True, "chars": 140},
                "critic": {"present": True, "chars": 80},
                "final": {"present": True, "chars": 36},
            },
        },
        active_memory_bundle={
            "schema": "ester.active_memory.v1",
            "stats": {
                "context_chars": 420,
                "sections_count": 5,
                "facts_count": 2,
                "recent_entries_count": 1,
                "has_profile": True,
                "has_honesty": True,
                "has_recent_doc": False,
                "has_retrieval": True,
            },
        },
        profile_snapshot={"summary": "Test User: Живёт в тестовом городе."},
        honesty_report={"label": "stable", "confidence": "high", "provenance_count": 1},
        provenance=[{"doc_id": "doc-1", "path": str(tmp_path / "doc.txt"), "page": 1}],
        safe_history=[{"role": "user", "content": "Что ты помнишь про меня?"}],
        has_file=True,
    )

    latest = json.loads(open(reply_trace.latest_path(), "r", encoding="utf-8").read())
    companion = json.loads(open(internal_trace_companion.companion_path(), "r", encoding="utf-8").read())
    coverage = json.loads(open(internal_trace_coverage.coverage_path(), "r", encoding="utf-8").read())
    diagnostics = json.loads(open(self_diagnostics.latest_path(), "r", encoding="utf-8").read())

    assert result["ok"] is True
    assert latest["schema"] == "ester.reply_trace.v1"
    assert latest["reply_mode"] == "cascade"
    assert latest["capture_priority"]["label"] in {"normal", "high", "critical"}
    assert companion["schema"] == "ester.internal_trace.companion.v1"
    assert companion["points_total"] >= 1
    assert coverage["schema"] == "ester.internal_trace.coverage.v1"
    assert diagnostics["schema"] == "ester.memory.self_diagnostics.v1"
