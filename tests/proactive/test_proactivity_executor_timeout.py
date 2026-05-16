# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.proactivity import executor as proactivity_executor


def test_run_once_core_marks_initiative_processed_on_max_work_timeout(monkeypatch):
    target = {
        "id": "initiative_timeout",
        "title": "Investigate repeated timeout",
        "text": "Check repeated max_work_ms_exceeded noise.",
        "kind": "repair_follow_up",
        "priority": "high",
        "source": "dialog",
    }
    marks = {}
    ticks = iter([0.0, 0.5])

    monkeypatch.setenv("ESTER_PROACTIVITY_ALLOW_ENQUEUE_IN_SLOT_A", "1")
    monkeypatch.setattr(proactivity_executor, "_select_initiative", lambda dry: dict(target))
    monkeypatch.setattr(
        proactivity_executor,
        "_gate_decide",
        lambda **kwargs: {"allowed": True, "reason_code": "", "reason": "ok"},
    )
    monkeypatch.setattr(proactivity_executor.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(proactivity_executor, "_queue_size", lambda: 0)
    monkeypatch.setattr(proactivity_executor, "_append_enqueue_log", lambda **kwargs: None)
    monkeypatch.setattr(proactivity_executor, "_update_runtime", lambda **kwargs: None)
    monkeypatch.setattr(
        proactivity_executor,
        "_mark_processed",
        lambda **kwargs: marks.update(kwargs) or {"ok": True},
    )

    rep = proactivity_executor._run_once_core(
        dry=False,
        requested_mode="enqueue",
        max_work_ms=200,
        max_queue_size=8,
        cooldown_sec=60,
    )

    assert rep["ok"] is True
    assert rep["reason"] == "max_work_ms_exceeded"
    assert marks["initiative_id"] == "initiative_timeout"
    assert marks["status"] == "planned_timeout"
    assert marks["note"] == "max_work_ms_exceeded"
