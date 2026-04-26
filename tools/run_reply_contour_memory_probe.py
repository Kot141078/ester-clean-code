# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run isolated reply contour memory probe.")
    parser.add_argument("--state-dir", default="", help="Optional state dir. Defaults to a temp directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    state_dir = str(args.state_dir or "").strip()
    temp_dir = None
    if not state_dir:
        temp_dir = tempfile.TemporaryDirectory(prefix="ester_reply_trace_probe_")
        state_dir = temp_dir.name
    os.environ["ESTER_STATE_DIR"] = state_dir

    repo_root = Path(__file__).resolve().parents[1]
    root_text = str(repo_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from modules.memory import active_context
    from modules.memory import internal_trace_coverage
    from modules.memory import profile_snapshot
    from modules.memory import recall_diagnostics
    from modules.memory import reply_trace
    from modules.memory import self_diagnostics
    from modules.memory import user_facts_store
    from modules.thinking.memory_self_observation import build_memory_self_observation

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе", "Любит проверяемые ответы"])
    snapshot = profile_snapshot.refresh_profile_snapshot("42", display_name="Test User", chat_id=777)
    bundle = active_context.build_active_memory_bundle(
        user_text="Что ты помнишь про меня?",
        evidence_memory="В профиле есть факт про тестовый город.",
        user_facts=["Живёт в тестовом городе", "Любит проверяемые ответы"],
        profile_context=profile_snapshot.render_profile_context(snapshot),
        honesty_block="[ACTIVE_MEMORY_HONESTY]\n- stance: stable\n- confidence: high",
    )
    recall_diagnostics.record_active_bundle(
        query="Что ты помнишь про меня?",
        user_id="42",
        chat_id="777",
        bundle=bundle,
        profile_snapshot=snapshot,
        provenance=[{"doc_id": "doc-1", "path": str(Path(state_dir) / "probe.txt"), "page": 1}],
    )
    trace = reply_trace.record_reply_trace(
        query="Что ты помнишь про меня?",
        reply_text="Я помню, что ты живёшь в тестовом городе и предпочитаешь проверяемые ответы.",
        user_id="42",
        chat_id="777",
        reply_mode="cascade",
        provider="probe",
        trace={
            "stage_order": ["brief", "draft", "critic", "final"],
            "stages": {
                "brief": {"present": True, "chars": 120},
                "draft": {"present": True, "chars": 180},
                "critic": {"present": True, "chars": 90},
                "final": {"present": True, "chars": 76},
            },
        },
        active_memory_bundle=bundle,
        profile_snapshot=snapshot,
        honesty_report={"label": "stable", "confidence": "high", "uncertainty_count": 0, "provenance_count": 1},
        provenance=[{"doc_id": "doc-1", "path": str(Path(state_dir) / "probe.txt"), "page": 1}],
        safe_history=[{"role": "user", "content": "Что ты помнишь про меня?"}],
        has_file=True,
    )
    coverage = internal_trace_coverage.ensure_materialized()
    diagnostics = self_diagnostics.ensure_materialized()
    memory_self = build_memory_self_observation("Что ты можешь сказать о своей памяти?", diagnostics=diagnostics)

    report = {
        "ok": True,
        "state_dir": state_dir,
        "trace_ready": bool(trace.get("ok")),
        "coverage_label": str(coverage.get("coverage_label") or ""),
        "diagnostics_status": str(diagnostics.get("status_label") or ""),
        "memory_self_present": "[MEMORY_SELF]" in str(memory_self or ""),
        "paths": {
            "reply_trace_latest": reply_trace.latest_path(),
            "reply_trace_history": reply_trace.history_path(),
            "self_diagnostics_latest": self_diagnostics.latest_path(),
            "coverage_path": internal_trace_coverage.coverage_path(),
        },
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if temp_dir is not None:
        temp_dir.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
