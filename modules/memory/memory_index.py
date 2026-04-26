# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _state_root() -> Path:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return Path(root).resolve()


def _diagnostics_dir() -> Path:
    path = (_state_root() / "data" / "memory" / "diagnostics" / "overview").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def overview_path() -> Path:
    return (_diagnostics_dir() / "overview.json").resolve()


def overview_digest_path() -> Path:
    return (_diagnostics_dir() / "overview.md").resolve()


def health_path() -> Path:
    return (_diagnostics_dir() / "health.json").resolve()


def health_digest_path() -> Path:
    return (_diagnostics_dir() / "health.md").resolve()


def timeline_path() -> Path:
    return (_diagnostics_dir() / "timeline.json").resolve()


def timeline_digest_path() -> Path:
    return (_diagnostics_dir() / "timeline.md").resolve()


def operator_path() -> Path:
    return (_diagnostics_dir() / "operator.json").resolve()


def operator_digest_path() -> Path:
    return (_diagnostics_dir() / "operator.md").resolve()


def history_path() -> Path:
    return (_diagnostics_dir() / "history.jsonl").resolve()


def _facts_dir() -> Path:
    return (_state_root() / "data" / "memory" / "user_facts" / "by_user").resolve()


def _profiles_dir() -> Path:
    return (_state_root() / "data" / "memory" / "profiles").resolve()


def _recent_docs_path() -> Path:
    return (_state_root() / "data" / "memory" / "recent_chat_docs.json").resolve()


def _recall_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "recall" / "latest.json").resolve()


def _deterministic_benchmark_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "recall" / "benchmarks" / "latest.json").resolve()


def _live_benchmark_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "recall" / "live" / "latest.json").resolve()


def _restart_benchmark_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "continuity" / "restart" / "latest.json").resolve()


def _semantic_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "consolidation" / "latest.json").resolve()


def _reply_trace_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "reply_trace" / "latest.json").resolve()


def _self_diagnostics_latest_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "self" / "latest.json").resolve()


def _internal_trace_companion_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "internal_trace" / "companion.json").resolve()


def _internal_trace_coverage_path() -> Path:
    return (_state_root() / "data" / "memory" / "diagnostics" / "internal_trace" / "coverage.json").resolve()


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    text = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        return
    except Exception:
        pass
    path.write_text(text, encoding="utf-8")


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(str(text or ""), encoding="utf-8")
        tmp.replace(path)
        return
    except Exception:
        pass
    path.write_text(str(text or ""), encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _read_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = str(line or "").strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    except Exception:
        return []
    return rows


def _append_history(row: Dict[str, Any]) -> None:
    keep_last = max(20, int(float(os.getenv("ESTER_MEMORY_OVERVIEW_HISTORY_LIMIT", "120") or 120)))
    min_append_sec = max(60, int(float(os.getenv("ESTER_MEMORY_OVERVIEW_MIN_APPEND_SEC", "300") or 300)))
    existing = _read_jsonl_rows(history_path())
    last = dict(existing[-1] or {}) if existing else {}
    last_ts = _as_int(last.get("ts") or 0)
    comparable_keys = (
        "status_label",
        "alerts_total",
        "users_total",
        "facts_total",
        "recent_doc_bindings_total",
        "honesty_label",
        "live_failed",
        "restart_failed",
        "deterministic_failed",
    )
    changed = any(row.get(key) != last.get(key) for key in comparable_keys)
    if (not changed) and last_ts > 0 and (int(row.get("ts") or 0) - last_ts) < min_append_sec:
        return

    lines = [json.dumps(item, ensure_ascii=False) for item in existing[-keep_last:]]
    lines.append(json.dumps(dict(row or {}), ensure_ascii=False))
    lines = lines[-keep_last:]
    text = ("\n".join(lines)).strip()
    if text:
        text += "\n"
    _atomic_write_text(history_path(), text)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _trim_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _facts_and_profiles_stats() -> Dict[str, Any]:
    facts_users_total = 0
    profiles_total = 0
    facts_total = 0
    known_users = set()

    facts_dir = _facts_dir()
    if facts_dir.is_dir():
        for path in sorted(facts_dir.glob("*.json")):
            payload = _load_json(path)
            facts = list(payload.get("facts") or []) if isinstance(payload.get("facts"), list) else []
            facts_total += len([item for item in facts if str(item or "").strip()])
            facts_users_total += 1
            known_users.add(path.stem)

    profiles_dir = _profiles_dir()
    if profiles_dir.is_dir():
        for path in sorted(profiles_dir.glob("*.json")):
            payload = _load_json(path)
            if payload:
                profiles_total += 1
                known_users.add(path.stem)

    return {
        "users_total": len(known_users),
        "facts_users_total": facts_users_total,
        "profiles_total": profiles_total,
        "facts_total": facts_total,
    }


def _recent_docs_stats() -> Dict[str, Any]:
    payload = _load_json(_recent_docs_path())
    by_chat = payload.get("by_chat") if isinstance(payload.get("by_chat"), dict) else {}
    bindings = payload.get("bindings") if isinstance(payload.get("bindings"), dict) else {}
    entries_total = 0
    for rows in by_chat.values():
        if isinstance(rows, list):
            entries_total += len([item for item in rows if isinstance(item, dict)])
    return {
        "recent_doc_chats_total": len(by_chat),
        "recent_doc_entries_total": entries_total,
        "recent_doc_bindings_total": len(bindings),
    }


def _extract_honesty_label(recall_latest: Dict[str, Any]) -> str:
    sections = recall_latest.get("sections") if isinstance(recall_latest, dict) else {}
    honesty_block = str((sections or {}).get("honesty") or "").strip()
    marker = "stance:"
    lowered = honesty_block.lower()
    idx = lowered.find(marker)
    if idx >= 0:
        tail = honesty_block[idx + len(marker) :].strip()
        token = str(tail.split()[0] or "").strip().strip(",;.")
        if token:
            return token.lower()
    for line in honesty_block.splitlines():
        raw = str(line or "").strip()
        if raw.lower().startswith("- stance:"):
            return str(raw.split(":", 1)[1] or "").strip().lower()
    return ""


def _benchmark_state(report: Dict[str, Any], *, schema: str) -> Dict[str, Any]:
    if not report:
        return {
            "schema": schema,
            "state": "missing",
            "cases_total": 0,
            "cases_passed": 0,
            "cases_failed": 0,
            "cases_skipped": 0,
            "ts": 0,
        }
    failed = _as_int(report.get("cases_failed") or 0)
    skipped = _as_int(report.get("cases_skipped") or 0)
    state = "passed"
    if failed > 0:
        state = "failed"
    elif skipped > 0:
        state = "partial"
    return {
        "schema": schema,
        "state": state,
        "ts": _as_int(report.get("ts") or 0),
        "cases_total": _as_int(report.get("cases_total") or 0),
        "cases_passed": _as_int(report.get("cases_passed") or 0),
        "cases_failed": failed,
        "cases_skipped": skipped,
    }


def _recall_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "schema": "ester.recall.diagnostic.v1",
            "state": "missing",
            "ts": 0,
            "query": "",
            "honesty_label": "",
            "provenance_count": 0,
        }
    return {
        "schema": "ester.recall.diagnostic.v1",
        "state": "ready",
        "ts": _as_int(report.get("ts") or 0),
        "query": _trim_text(report.get("query") or "", 180),
        "honesty_label": _extract_honesty_label(report),
        "provenance_count": _as_int(report.get("provenance_count") or 0),
        "profile_summary": _trim_text(report.get("profile_summary") or "", 180),
    }


def _semantic_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "schema": "ester.memory.semantic_consolidation.v1",
            "state": "missing",
            "ts": 0,
            "users_count": 0,
            "facts_count": 0,
            "top_terms": [],
        }
    return {
        "schema": "ester.memory.semantic_consolidation.v1",
        "state": "ready",
        "ts": _as_int(report.get("ts") or 0),
        "users_count": _as_int(report.get("users_count") or 0),
        "facts_count": _as_int(report.get("facts_count") or 0),
        "top_terms": [dict(item) for item in list(report.get("top_terms") or [])[:5] if isinstance(item, dict)],
    }


def _reply_trace_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "schema": "ester.reply_trace.v1",
            "state": "missing",
            "ts": 0,
            "reply_mode": "",
            "reasoning_bias_label": "",
            "capture_priority_label": "",
        }
    return {
        "schema": "ester.reply_trace.v1",
        "state": "ready",
        "ts": _as_int(report.get("ts") or 0),
        "reply_mode": str(report.get("reply_mode") or ""),
        "reasoning_bias_label": str((dict(report.get("reasoning_bias") or {})).get("label") or ""),
        "capture_priority_label": str((dict(report.get("capture_priority") or {})).get("label") or ""),
        "capture_pressure_label": str((dict(report.get("capture_pressure") or {})).get("label") or ""),
        "reply_chars": _as_int(report.get("reply_chars") or 0),
        "contour_stage_count": _as_int((dict(report.get("contour") or {})).get("stage_count") or 0),
    }


def _self_diagnostics_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "schema": "ester.memory.self_diagnostics.v1",
            "state": "missing",
            "ts": 0,
            "status_label": "",
            "introspection_label": "",
        }
    return {
        "schema": "ester.memory.self_diagnostics.v1",
        "state": "ready",
        "ts": _as_int(report.get("generated_ts") or 0),
        "status_label": str(report.get("status_label") or ""),
        "introspection_label": str(report.get("introspection_label") or ""),
        "trace_bias_label": str(report.get("trace_bias_label") or ""),
        "trace_coverage_label": str(report.get("trace_coverage_label") or ""),
    }


def _internal_trace_companion_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "schema": "ester.internal_trace.companion.v1",
            "state": "missing",
            "generated_ts": 0,
            "points_total": 0,
            "dominant_bias_label": "",
        }
    return {
        "schema": "ester.internal_trace.companion.v1",
        "state": "ready",
        "generated_ts": _as_int(report.get("generated_ts") or 0),
        "points_total": _as_int(report.get("points_total") or 0),
        "dominant_bias_label": str(report.get("dominant_bias_label") or ""),
        "dominant_reply_mode": str(report.get("dominant_reply_mode") or ""),
        "trend_label": str((dict(report.get("trend") or {})).get("label") or ""),
    }


def _internal_trace_coverage_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "schema": "ester.internal_trace.coverage.v1",
            "state": "missing",
            "generated_ts": 0,
            "coverage_label": "",
            "coverage_score": 0,
        }
    return {
        "schema": "ester.internal_trace.coverage.v1",
        "state": "ready",
        "generated_ts": _as_int(report.get("generated_ts") or 0),
        "coverage_label": str(report.get("coverage_label") or ""),
        "coverage_score": _as_int(report.get("coverage_score") or 0),
        "points_total": _as_int(report.get("points_total") or 0),
    }


def _age_sec(ts: int, now_ts: int) -> int:
    if ts <= 0:
        return -1
    return max(0, int(now_ts) - int(ts))


def _build_alerts(
    *,
    now_ts: int,
    storage: Dict[str, Any],
    recall: Dict[str, Any],
    reply_trace: Dict[str, Any],
    self_diagnostics: Dict[str, Any],
    companion: Dict[str, Any],
    coverage: Dict[str, Any],
    deterministic: Dict[str, Any],
    live: Dict[str, Any],
    restart: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    alerts: List[Dict[str, Any]] = []
    highlights: List[str] = []

    def add(code: str, severity: int, message: str) -> None:
        alerts.append({"code": code, "severity": int(severity), "message": str(message)})

    if storage.get("users_total", 0) <= 0 and storage.get("recent_doc_bindings_total", 0) <= 0:
        add("memory_sparse", 30, "В памяти пока мало materialized пользовательских профилей и recent-doc bindings.")
    if recall.get("state") != "ready":
        add("missing_recall_diagnostic", 55, "Нет latest recall diagnostic для active-memory bundle.")
    else:
        recall_age = _age_sec(_as_int(recall.get("ts") or 0), now_ts)
        if recall_age > 86400:
            add("stale_recall_diagnostic", 35, f"Latest recall diagnostic старше суток: {recall_age} sec.")
        honesty_label = str(recall.get("honesty_label") or "").strip()
        if honesty_label in {"uncertain", "missing"}:
            add(f"memory_honesty_{honesty_label}", 25, f"Latest memory honesty stance = {honesty_label}.")

    if recall.get("state") == "ready" and reply_trace.get("state") != "ready":
        add("missing_reply_trace", 45, "Есть recall diagnostic, но нет latest reply trace contour.")
    elif reply_trace.get("state") == "ready":
        trace_age = _age_sec(_as_int(reply_trace.get("ts") or 0), now_ts)
        if trace_age > 86400:
            add("stale_reply_trace", 25, f"Latest reply trace старше суток: {trace_age} sec.")

    if reply_trace.get("state") == "ready" and self_diagnostics.get("state") != "ready":
        add("missing_self_diagnostics", 40, "Есть reply trace, но нет latest memory self-diagnostics.")

    if str(coverage.get("coverage_label") or "") in {"low", "empty"}:
        add("trace_coverage_low", 35, "Internal trace coverage остаётся низким или пустым.")

    if str(companion.get("trend_label") or "") == "grounding_thinning":
        add("trace_grounding_thinning", 25, "Trace trend показывает thinning grounding по recent history.")

    if deterministic.get("state") == "failed":
        add("deterministic_benchmark_failed", 80, "Deterministic recall benchmark содержит failing cases.")
    if live.get("state") == "failed":
        add("live_benchmark_failed", 85, "Live recall benchmark содержит failing cases.")
    elif live.get("state") == "partial":
        add("live_benchmark_partial", 25, "Live recall benchmark прошёл не полностью и содержит skipped cases.")
    elif live.get("state") == "missing":
        add("live_benchmark_missing", 25, "Live recall benchmark ещё не materialized.")

    if restart.get("state") == "failed":
        add("restart_continuity_failed", 90, "Restart continuity benchmark содержит failing cases.")
    elif restart.get("state") == "partial":
        add("restart_continuity_partial", 30, "Restart continuity benchmark частичный и содержит skipped cases.")
    elif restart.get("state") == "missing" and storage.get("recent_doc_bindings_total", 0) > 0:
        add("restart_continuity_missing", 35, "Есть recent-doc bindings, но нет latest restart continuity benchmark.")

    alerts.sort(key=lambda item: (-_as_int(item.get("severity") or 0), str(item.get("code") or "")))
    top_codes = [str(item.get("code") or "") for item in alerts[:6]]

    if alerts:
        highlights.append(f"alerts={len(alerts)} top={', '.join(top_codes[:3])}")
    else:
        highlights.append("memory diagnostics look healthy")
    if storage.get("users_total", 0) > 0:
        highlights.append(
            "users=%s facts=%s profiles=%s"
            % (
                int(storage.get("users_total") or 0),
                int(storage.get("facts_total") or 0),
                int(storage.get("profiles_total") or 0),
            )
        )
    if storage.get("recent_doc_bindings_total", 0) > 0:
        highlights.append(
            "recent_docs=%s bindings=%s"
            % (
                int(storage.get("recent_doc_entries_total") or 0),
                int(storage.get("recent_doc_bindings_total") or 0),
            )
        )

    status_label = "healthy"
    max_severity = max([_as_int(item.get("severity") or 0) for item in alerts] or [0])
    if max_severity >= 80:
        status_label = "degraded"
    elif alerts:
        status_label = "attention"
    elif storage.get("users_total", 0) <= 0 and storage.get("recent_doc_bindings_total", 0) <= 0:
        status_label = "sparse"

    return status_label, alerts, highlights


def _trend_label(rows: List[Dict[str, Any]]) -> str:
    if len(rows) < 2:
        return "initial"
    first = dict(rows[0] or {})
    last = dict(rows[-1] or {})
    first_alerts = _as_int(first.get("alerts_total") or 0)
    last_alerts = _as_int(last.get("alerts_total") or 0)
    if last_alerts < first_alerts:
        return "improving"
    if last_alerts > first_alerts:
        return "degraded"
    if str(last.get("status_label") or "") == "healthy":
        return "healthy"
    return "stable"


def _render_overview_markdown(payload: Dict[str, Any]) -> str:
    storage = dict(payload.get("storage") or {})
    latest = dict(payload.get("latest") or {})
    health = dict(payload.get("health") or {})
    lines = [
        "# memory overview",
        "",
        f"- status: {str(health.get('status_label') or 'unknown')}",
        f"- trend: {str(health.get('trend_label') or 'initial')}",
        f"- users_total: {int(storage.get('users_total') or 0)}",
        f"- facts_total: {int(storage.get('facts_total') or 0)}",
        f"- profiles_total: {int(storage.get('profiles_total') or 0)}",
        f"- recent_doc_bindings_total: {int(storage.get('recent_doc_bindings_total') or 0)}",
        "",
        "## latest diagnostics",
        f"- recall: {str((latest.get('recall') or {}).get('state') or 'missing')}",
        f"- reply_trace: {str((latest.get('reply_trace') or {}).get('state') or 'missing')}",
        f"- self_diagnostics: {str((latest.get('self_diagnostics') or {}).get('state') or 'missing')}",
        f"- deterministic_benchmark: {str((latest.get('deterministic_benchmark') or {}).get('state') or 'missing')}",
        f"- live_benchmark: {str((latest.get('live_benchmark') or {}).get('state') or 'missing')}",
        f"- restart_continuity: {str((latest.get('restart_continuity') or {}).get('state') or 'missing')}",
        f"- semantic_consolidation: {str((latest.get('semantic_consolidation') or {}).get('state') or 'missing')}",
        "",
        "## highlights",
    ]
    highlights = [str(item) for item in list(payload.get("highlights") or []) if str(item).strip()]
    if highlights:
        for item in highlights[:8]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "_c=a+b_"])
    return "\n".join(lines).strip() + "\n"


def _render_health_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# memory health digest",
        "",
        f"- status: {str(payload.get('status_label') or 'unknown')}",
        f"- trend: {str(payload.get('trend_label') or 'initial')}",
        f"- alerts_total: {int(payload.get('alerts_total') or 0)}",
        f"- latest_honesty_label: {str(payload.get('latest_honesty_label') or '')}",
        "",
        "## alerts",
    ]
    alerts = [dict(item) for item in list(payload.get("alerts") or []) if isinstance(item, dict)]
    if alerts:
        for item in alerts[:12]:
            lines.append(
                "- [%s] severity=%s %s"
                % (
                    str(item.get("code") or ""),
                    int(item.get("severity") or 0),
                    str(item.get("message") or ""),
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "_c=a+b_"])
    return "\n".join(lines).strip() + "\n"


def _render_timeline_markdown(payload: Dict[str, Any]) -> str:
    latest_state = dict(payload.get("latest_state") or {})
    lines = [
        "# memory timeline",
        "",
        f"- trend: {str(payload.get('trend_label') or 'initial')}",
        f"- points: {int(payload.get('points_total') or 0)}",
        f"- latest_status: {str(latest_state.get('status_label') or 'unknown')}",
        "",
        "## recent points",
    ]
    for row in [dict(item) for item in list(payload.get("points") or [])[:12] if isinstance(item, dict)]:
        lines.append(
            "- ts=%s status=%s alerts=%s users=%s facts=%s honesty=%s"
            % (
                int(row.get("ts") or 0),
                str(row.get("status_label") or ""),
                int(row.get("alerts_total") or 0),
                int(row.get("users_total") or 0),
                int(row.get("facts_total") or 0),
                str(row.get("honesty_label") or ""),
            )
        )
    if len(lines) == 6:
        lines.append("- none")
    lines.extend(["", "_c=a+b_"])
    return "\n".join(lines).strip() + "\n"


def _build_operator(overview: Dict[str, Any], health: Dict[str, Any], timeline: Dict[str, Any]) -> Dict[str, Any]:
    src = dict(overview or {})
    storage = dict(src.get("storage") or {})
    latest = dict(src.get("latest") or {})
    alerts = [dict(item or {}) for item in list((dict(health or {})).get("alerts") or []) if isinstance(item, dict)]
    timeline_rows = [dict(item or {}) for item in list((dict(timeline or {})).get("points") or []) if isinstance(item, dict)]
    latest_recall = dict(latest.get("recall") or {})
    latest_reply_trace = dict(latest.get("reply_trace") or {})
    latest_self_diag = dict(latest.get("self_diagnostics") or {})
    latest_live = dict(latest.get("live_benchmark") or {})
    latest_restart = dict(latest.get("restart_continuity") or {})
    latest_deterministic = dict(latest.get("deterministic_benchmark") or {})

    top_actions: List[Dict[str, Any]] = []
    for row in alerts[:8]:
        code = str(row.get("code") or "").strip()
        severity = _as_int(row.get("severity") or 0)
        message = str(row.get("message") or "").strip()
        command = ""
        inspect_path = str(overview_path())
        if code in {"missing_recall_diagnostic", "stale_recall_diagnostic"}:
            command = "python tools/memory_status.py --json --section overview"
            inspect_path = str(_recall_latest_path())
        elif code in {"missing_reply_trace", "stale_reply_trace"}:
            command = "python tools/memory_status.py --json --section reply_trace"
            inspect_path = str(_reply_trace_latest_path())
        elif code == "missing_self_diagnostics":
            command = "python tools/memory_status.py --json --section self_diagnostics"
            inspect_path = str(_self_diagnostics_latest_path())
        elif code == "trace_coverage_low":
            command = "python tools/run_reply_contour_memory_probe.py --json"
            inspect_path = str(_internal_trace_coverage_path())
        elif code in {"live_benchmark_failed", "live_benchmark_partial", "live_benchmark_missing"}:
            command = "python tools/run_live_recall_benchmark.py"
            inspect_path = str(_live_benchmark_latest_path())
        elif code in {"restart_continuity_failed", "restart_continuity_partial", "restart_continuity_missing"}:
            command = "python tools/run_restart_continuity_benchmark.py"
            inspect_path = str(_restart_benchmark_latest_path())
        elif code == "deterministic_benchmark_failed":
            command = "python tools/run_recall_benchmark.py"
            inspect_path = str(_deterministic_benchmark_latest_path())
        elif code == "memory_sparse":
            command = "python tools/memory_status.py --json --section overview"
            inspect_path = str(overview_path())
        top_actions.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "inspect_path": inspect_path,
                "suggested_command": command,
            }
        )

    suggested_queries = [
        {
            "label": "overview",
            "command": "python tools/memory_status.py --json --section overview",
        },
        {
            "label": "health",
            "command": "python tools/memory_status.py --json --section health",
        },
        {
            "label": "timeline",
            "command": "python tools/memory_status.py --json --section timeline",
        },
    ]
    if str(latest_live.get("state") or "") != "passed":
        suggested_queries.append(
            {
                "label": "live_benchmark",
                "command": "python tools/run_live_recall_benchmark.py",
            }
        )
    if str(latest_restart.get("state") or "") != "passed":
        suggested_queries.append(
            {
                "label": "restart_benchmark",
                "command": "python tools/run_restart_continuity_benchmark.py",
            }
        )
    if str(latest_deterministic.get("state") or "") != "passed":
        suggested_queries.append(
            {
                "label": "deterministic_benchmark",
                "command": "python tools/run_recall_benchmark.py",
            }
        )
    if str(latest_reply_trace.get("state") or "") != "ready" or str(latest_self_diag.get("state") or "") != "ready":
        suggested_queries.append(
            {
                "label": "reply_contour_probe",
                "command": "python tools/run_reply_contour_memory_probe.py --json",
            }
        )

    recent_statuses = [str(row.get("status_label") or "") for row in timeline_rows[-5:] if str(row.get("status_label") or "").strip()]
    return {
        "schema": "ester.memory.operator.v1",
        "generated_ts": int(time.time()),
        "status_label": str((dict(health or {})).get("status_label") or "unknown"),
        "trend_label": str((dict(health or {})).get("trend_label") or "initial"),
        "attention_needed": bool(alerts),
        "alerts_total": len(alerts),
        "latest_honesty_label": str(latest_recall.get("honesty_label") or ""),
        "latest_trace_bias_label": str(latest_self_diag.get("trace_bias_label") or ""),
        "users_total": _as_int(storage.get("users_total") or 0),
        "facts_total": _as_int(storage.get("facts_total") or 0),
        "recent_doc_bindings_total": _as_int(storage.get("recent_doc_bindings_total") or 0),
        "recent_statuses": recent_statuses,
        "top_actions": top_actions,
        "suggested_queries": suggested_queries[:8],
        "source_paths": {
            "overview_path": str(overview_path()),
            "health_path": str(health_path()),
            "timeline_path": str(timeline_path()),
            "recall_latest_path": str(_recall_latest_path()),
            "reply_trace_latest_path": str(_reply_trace_latest_path()),
            "self_diagnostics_latest_path": str(_self_diagnostics_latest_path()),
            "live_benchmark_latest_path": str(_live_benchmark_latest_path()),
            "restart_benchmark_latest_path": str(_restart_benchmark_latest_path()),
        },
    }


def _render_operator_markdown(payload: Dict[str, Any]) -> str:
    src = dict(payload or {})
    lines = [
        "# memory operator",
        "",
        f"- status: {str(src.get('status_label') or 'unknown')}",
        f"- trend: {str(src.get('trend_label') or 'initial')}",
        f"- attention_needed: {str(bool(src.get('attention_needed'))).lower()}",
        f"- alerts_total: {int(src.get('alerts_total') or 0)}",
        f"- latest_honesty_label: {str(src.get('latest_honesty_label') or '')}",
        f"- latest_trace_bias_label: {str(src.get('latest_trace_bias_label') or '')}",
        "",
        "## top actions",
    ]
    actions = [dict(item or {}) for item in list(src.get("top_actions") or []) if isinstance(item, dict)]
    if actions:
        for item in actions:
            cmd = str(item.get("suggested_command") or "").strip()
            inspect_path = str(item.get("inspect_path") or "").strip()
            tail = f" command=`{cmd}`" if cmd else ""
            if inspect_path:
                tail += f" inspect=`{inspect_path}`"
            lines.append(
                f"- [sev {int(item.get('severity') or 0)}] {str(item.get('code') or '')}: {str(item.get('message') or '')}{tail}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## suggested queries"])
    suggestions = [dict(item or {}) for item in list(src.get("suggested_queries") or []) if isinstance(item, dict)]
    if suggestions:
        for item in suggestions:
            lines.append(f"- {str(item.get('label') or '')}: `{str(item.get('command') or '')}`")
    else:
        lines.append("- none")
    lines.extend(["", "_c=a+b_"])
    return "\n".join(lines).strip() + "\n"


def ensure_materialized() -> Dict[str, Any]:
    now_ts = int(time.time())
    storage = {}
    storage.update(_facts_and_profiles_stats())
    storage.update(_recent_docs_stats())

    recall_latest = _load_json(_recall_latest_path())
    reply_trace_latest = _load_json(_reply_trace_latest_path())
    self_diagnostics_latest = _load_json(_self_diagnostics_latest_path())
    companion_latest = _load_json(_internal_trace_companion_path())
    coverage_latest = _load_json(_internal_trace_coverage_path())
    deterministic_latest = _load_json(_deterministic_benchmark_latest_path())
    live_latest = _load_json(_live_benchmark_latest_path())
    restart_latest = _load_json(_restart_benchmark_latest_path())
    semantic_latest = _load_json(_semantic_latest_path())

    recall_summary = _recall_summary(recall_latest)
    reply_trace_summary = _reply_trace_summary(reply_trace_latest)
    self_diagnostics_summary = _self_diagnostics_summary(self_diagnostics_latest)
    companion_summary = _internal_trace_companion_summary(companion_latest)
    coverage_summary = _internal_trace_coverage_summary(coverage_latest)
    deterministic_summary = _benchmark_state(deterministic_latest, schema="ester.recall.benchmark.v1")
    live_summary = _benchmark_state(live_latest, schema="ester.live_recall.benchmark.v1")
    restart_summary = _benchmark_state(restart_latest, schema="ester.restart_continuity.benchmark.v1")
    semantic_summary = _semantic_summary(semantic_latest)

    status_label, alerts, highlights = _build_alerts(
        now_ts=now_ts,
        storage=storage,
        recall=recall_summary,
        reply_trace=reply_trace_summary,
        self_diagnostics=self_diagnostics_summary,
        companion=companion_summary,
        coverage=coverage_summary,
        deterministic=deterministic_summary,
        live=live_summary,
        restart=restart_summary,
    )

    history_row = {
        "ts": now_ts,
        "status_label": status_label,
        "alerts_total": len(alerts),
        "users_total": int(storage.get("users_total") or 0),
        "facts_total": int(storage.get("facts_total") or 0),
        "recent_doc_bindings_total": int(storage.get("recent_doc_bindings_total") or 0),
        "honesty_label": str(recall_summary.get("honesty_label") or ""),
        "reply_trace_state": str(reply_trace_summary.get("state") or ""),
        "self_diagnostics_state": str(self_diagnostics_summary.get("state") or ""),
        "live_failed": int(live_summary.get("cases_failed") or 0),
        "restart_failed": int(restart_summary.get("cases_failed") or 0),
        "deterministic_failed": int(deterministic_summary.get("cases_failed") or 0),
    }
    _append_history(history_row)
    rows = _read_jsonl_rows(history_path())
    trend = _trend_label(rows[-12:])

    health = {
        "schema": "ester.memory.health.v1",
        "generated_ts": now_ts,
        "status_label": status_label,
        "trend_label": trend,
        "alerts_total": len(alerts),
        "alert_codes": [str(item.get("code") or "") for item in alerts],
        "latest_honesty_label": str(recall_summary.get("honesty_label") or ""),
        "latest_trace_bias_label": str(self_diagnostics_summary.get("trace_bias_label") or ""),
        "alerts": alerts,
        "coverage": {
            "users_total": int(storage.get("users_total") or 0),
            "facts_users_total": int(storage.get("facts_users_total") or 0),
            "profiles_total": int(storage.get("profiles_total") or 0),
            "recent_doc_bindings_total": int(storage.get("recent_doc_bindings_total") or 0),
            "reply_trace_state": str(reply_trace_summary.get("state") or ""),
            "self_diagnostics_state": str(self_diagnostics_summary.get("state") or ""),
            "internal_trace_coverage_label": str(coverage_summary.get("coverage_label") or ""),
        },
        "benchmark_states": {
            "deterministic": dict(deterministic_summary),
            "live": dict(live_summary),
            "restart": dict(restart_summary),
        },
    }

    overview = {
        "schema": "ester.memory.overview.v1",
        "generated_ts": now_ts,
        "storage": storage,
        "latest": {
            "recall": recall_summary,
            "reply_trace": reply_trace_summary,
            "self_diagnostics": self_diagnostics_summary,
            "internal_trace_companion": companion_summary,
            "internal_trace_coverage": coverage_summary,
            "deterministic_benchmark": deterministic_summary,
            "live_benchmark": live_summary,
            "restart_continuity": restart_summary,
            "semantic_consolidation": semantic_summary,
        },
        "health": {
            "status_label": status_label,
            "trend_label": trend,
            "alerts_total": len(alerts),
            "alert_codes": [str(item.get("code") or "") for item in alerts],
            "latest_honesty_label": str(recall_summary.get("honesty_label") or ""),
        },
        "highlights": highlights,
    }

    timeline = {
        "schema": "ester.memory.timeline.v1",
        "generated_ts": now_ts,
        "trend_label": trend,
        "points_total": len(rows),
        "latest_state": history_row,
        "points": rows[-24:],
    }
    operator = _build_operator(overview, health, timeline)

    _atomic_write_json(overview_path(), overview)
    _atomic_write_text(overview_digest_path(), _render_overview_markdown(overview))
    _atomic_write_json(health_path(), health)
    _atomic_write_text(health_digest_path(), _render_health_markdown(health))
    _atomic_write_json(timeline_path(), timeline)
    _atomic_write_text(timeline_digest_path(), _render_timeline_markdown(timeline))
    _atomic_write_json(operator_path(), operator)
    _atomic_write_text(operator_digest_path(), _render_operator_markdown(operator))

    return {
        "ok": True,
        "overview": overview,
        "health": health,
        "timeline": timeline,
        "operator": operator,
    }


__all__ = [
    "ensure_materialized",
    "overview_path",
    "overview_digest_path",
    "health_path",
    "health_digest_path",
    "timeline_path",
    "timeline_digest_path",
    "operator_path",
    "operator_digest_path",
    "history_path",
]
