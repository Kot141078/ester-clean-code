from __future__ import annotations

from modules.memory.memory_honesty import evaluate_memory_honesty, render_memory_honesty_block


def test_memory_honesty_marks_missing_when_no_evidence():
    report = evaluate_memory_honesty(
        bundle_stats={"recent_entries_count": 0, "has_retrieval": False},
        user_facts=[],
        profile_snapshot={},
        retrieval_stats={},
        provenance=[],
    )

    assert report["label"] == "missing"
    assert report["confidence"] == "low"
    block = render_memory_honesty_block(report)
    assert "[ACTIVE_MEMORY_HONESTY]" in block
    assert "missing" in block


def test_memory_honesty_marks_uncertain_when_doc_uncertainty_present():
    report = evaluate_memory_honesty(
        bundle_stats={"recent_entries_count": 1, "has_retrieval": True},
        user_facts=["Живёт в тестовом городе"],
        profile_snapshot={"summary": "Test User: Живёт в тестовом городе."},
        retrieval_stats={"resolved_doc": True, "doc_uncertainty_count": 2},
        retrieval_uncertainty=[{"name": "near_match.md"}],
        provenance=[{"doc_id": "abc"}],
    )

    assert report["label"] == "uncertain"
    assert report["uncertainty_count"] >= 3
