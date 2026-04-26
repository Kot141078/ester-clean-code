# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.memory.active_context import build_active_memory_bundle
from modules.memory.profile_snapshot import (
    list_known_user_ids,
    load_profile_snapshot,
    render_profile_context,
)
from modules.memory.user_facts_store import load_user_facts
from modules.telegram_runtime_helpers import passport_record_to_short_term_messages


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _default_cases_path() -> str:
    return os.path.join(_state_root(), "config", "restart_continuity_benchmark_cases.json")


def _bench_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "continuity", "restart")


def _passport_path() -> str:
    custom = (os.environ.get("ESTER_PASSPORT_PATH") or "").strip()
    if custom:
        return str(Path(os.path.expandvars(os.path.expanduser(custom))))
    return str(Path(_state_root()) / "data" / "passport" / "clean_memory.jsonl")


def _recent_docs_path() -> str:
    return os.path.join(_state_root(), "data", "memory", "recent_chat_docs.json")


def _load_cases(path: Optional[str] = None) -> List[Dict[str, Any]]:
    case_path = str(path or _default_cases_path()).strip()
    if not case_path or not os.path.exists(case_path):
        return []
    try:
        with open(case_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        cases = data.get("cases") if isinstance(data, dict) else data
        if isinstance(cases, list):
            return [dict(item) for item in cases if isinstance(item, dict)]
    except Exception:
        pass
    return []


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _trim_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _tail_lines(path: str, *, max_lines: int) -> List[str]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [str(line or "").rstrip("\r\n") for line in f.readlines()[-max(1, int(max_lines)) :]]
    except Exception:
        return []


def _passport_schema(rec: Dict[str, Any]) -> str:
    if any(key in rec for key in ("role_user", "role_assistant")):
        return "role_schema"
    if any(key in rec for key in ("user", "assistant")):
        return "plain_schema"
    return "other"


def _restore_passport_tail(path: str, *, max_lines: int) -> Dict[str, Any]:
    restored: List[Dict[str, str]] = []
    schemas_seen: List[str] = []
    records_scanned = 0

    for line in _tail_lines(path, max_lines=max_lines):
        line = str(line or "").strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        records_scanned += 1
        schema = _passport_schema(rec)
        if schema not in schemas_seen:
            schemas_seen.append(schema)
        for msg in passport_record_to_short_term_messages(rec):
            role = str(msg.get("role") or "").strip()
            content = _trim_text(msg.get("content") or "", 280)
            if role in ("user", "assistant") and content:
                restored.append({"role": role, "content": content})

    return {
        "records_scanned": records_scanned,
        "schemas_seen": schemas_seen,
        "messages": restored,
    }


def _resolve_first_profile_case() -> Optional[Dict[str, Any]]:
    for user_id in list_known_user_ids(limit=50):
        facts = list(load_user_facts(user_id, include_legacy=False) or [])
        snapshot = load_profile_snapshot(user_id)
        if facts or snapshot:
            return {
                "user_id": user_id,
                "chat_id": str(snapshot.get("last_chat_id") or ""),
                "facts": facts,
                "profile": snapshot,
            }
    return None


def _load_recent_docs_store() -> Dict[str, Any]:
    path = _recent_docs_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _resolve_first_recent_doc_case() -> Optional[Dict[str, Any]]:
    store = _load_recent_docs_store()
    by_chat = store.get("by_chat") if isinstance(store, dict) else {}
    bindings = store.get("bindings") if isinstance(store, dict) else {}
    if not isinstance(by_chat, dict):
        return None
    if not isinstance(bindings, dict):
        bindings = {}

    for raw_chat_id, entries in by_chat.items():
        try:
            chat_id = int(str(raw_chat_id))
        except Exception:
            continue
        if not isinstance(entries, list) or not entries:
            continue
        entry = next((dict(item) for item in entries if isinstance(item, dict)), None)
        if not isinstance(entry, dict):
            continue
        binding = {}
        direct_key = f"{chat_id}:"
        if isinstance(bindings.get(direct_key), dict):
            binding = dict(bindings.get(direct_key) or {})
        else:
            for key, value in bindings.items():
                if str(key).startswith(f"{chat_id}:") and isinstance(value, dict):
                    binding = dict(value)
                    break
        name = str(entry.get("name") or binding.get("orig_name") or binding.get("title") or "").strip()
        if not name:
            continue
        return {
            "chat_id": str(chat_id),
            "entry": entry,
            "binding": binding,
            "name": name,
        }
    return None


def _render_recent_doc_continuity(entry: Dict[str, Any], binding: Dict[str, Any]) -> str:
    name = str(entry.get("name") or binding.get("orig_name") or binding.get("title") or "").strip()
    summary = _trim_text(entry.get("summary") or "", 1200)
    citations = [str(item or "").strip() for item in list(entry.get("citations") or []) if str(item or "").strip()]
    source_path = _trim_text(binding.get("source_path") or entry.get("source_path") or "", 220)

    lines: List[str] = []
    if name:
        lines.append(f"Недавний документ: {name}")
    if summary:
        lines.append(f"Кратко: {summary}")
    if citations:
        lines.append("Цитаты:")
        lines.extend(f"- {item}" for item in citations[:3])
    if source_path:
        lines.append(f"Источник: {source_path}")
    return "\n".join(lines).strip()


def _run_passport_tail_restore_case(case_id: str, *, max_lines: int = 500) -> Dict[str, Any]:
    path = _passport_path()
    if not os.path.exists(path):
        return {"id": case_id, "status": "skipped", "reason": "passport_not_found", "path": path}

    restored = _restore_passport_tail(path, max_lines=max_lines)
    messages = list(restored.get("messages") or [])
    roles_seen = sorted({str(item.get("role") or "") for item in messages if str(item.get("role") or "").strip()})
    last_user = next((item.get("content") for item in reversed(messages) if item.get("role") == "user"), "")
    last_assistant = next((item.get("content") for item in reversed(messages) if item.get("role") == "assistant"), "")
    missing: List[str] = []
    if not messages:
        missing.append("restored_messages")
    if not roles_seen:
        missing.append("roles_seen")

    return {
        "id": case_id,
        "status": "passed" if not missing else "failed",
        "path": path,
        "restored_messages": len(messages),
        "records_scanned": int(restored.get("records_scanned") or 0),
        "schemas_seen": list(restored.get("schemas_seen") or []),
        "roles_seen": roles_seen,
        "last_user_excerpt": _trim_text(last_user, 180),
        "last_assistant_excerpt": _trim_text(last_assistant, 180),
        "missing": missing,
    }


def _run_first_user_profile_case(case_id: str) -> Dict[str, Any]:
    resolved = _resolve_first_profile_case()
    if not resolved:
        return {"id": case_id, "status": "skipped", "reason": "no_profile_or_facts"}

    user_id = str(resolved.get("user_id") or "")
    chat_id = str(resolved.get("chat_id") or "")
    facts = list(resolved.get("facts") or [])
    snapshot = dict(resolved.get("profile") or {})
    bundle = build_active_memory_bundle(
        user_text="Что ты про меня помнишь?",
        evidence_memory="",
        user_facts=facts,
        profile_context=render_profile_context(snapshot),
    )
    context = str(bundle.get("context") or "")
    missing: List[str] = []
    first_fact = str((facts or [""])[0] or "").strip()
    if snapshot and "[ACTIVE_USER_PROFILE]" not in context:
        missing.append("[ACTIVE_USER_PROFILE]")
    if facts and "[ACTIVE_USER_FACTS]" not in context:
        missing.append("[ACTIVE_USER_FACTS]")
    if first_fact and first_fact not in context:
        missing.append(first_fact)

    return {
        "id": case_id,
        "status": "passed" if not missing else "failed",
        "user_id": user_id,
        "chat_id": chat_id,
        "facts_count": len(facts),
        "profile_summary": _trim_text(snapshot.get("summary") or "", 180),
        "missing": missing,
        "stats": dict(bundle.get("stats") or {}),
    }


def _run_first_recent_doc_binding_case(case_id: str) -> Dict[str, Any]:
    resolved = _resolve_first_recent_doc_case()
    if not resolved:
        return {"id": case_id, "status": "skipped", "reason": "no_recent_doc_binding"}

    entry = dict(resolved.get("entry") or {})
    binding = dict(resolved.get("binding") or {})
    name = str(resolved.get("name") or "").strip()
    recent_doc_context = _render_recent_doc_continuity(entry, binding)
    bundle = build_active_memory_bundle(
        user_text=f"Напомни по недавнему файлу {name}",
        evidence_memory="",
        recent_doc_context=recent_doc_context,
    )
    context = str(bundle.get("context") or "")
    missing: List[str] = []
    if "[ACTIVE_RECENT_DOCUMENT]" not in context:
        missing.append("[ACTIVE_RECENT_DOCUMENT]")
    if name and name not in context:
        missing.append(name)

    return {
        "id": case_id,
        "status": "passed" if not missing else "failed",
        "chat_id": str(resolved.get("chat_id") or ""),
        "doc_name": name,
        "summary_preview": _trim_text(entry.get("summary") or "", 180),
        "missing": missing,
        "stats": dict(bundle.get("stats") or {}),
    }


def run_restart_benchmark(
    cases: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    cases_path: Optional[str] = None,
) -> Dict[str, Any]:
    corpus = [dict(item) for item in (cases or _load_cases(cases_path))]
    if not corpus:
        corpus = [
            {"id": "restart_passport_tail_restore", "kind": "passport_tail_restore"},
            {"id": "restart_first_user_profile", "kind": "first_user_profile"},
            {"id": "restart_first_recent_doc_binding", "kind": "first_recent_doc_binding"},
        ]

    results: List[Dict[str, Any]] = []
    for case in corpus:
        kind = str(case.get("kind") or "").strip().lower()
        case_id = str(case.get("id") or kind or f"case_{len(results)+1}")
        if kind == "passport_tail_restore":
            max_lines = int(case.get("max_lines") or 500)
            results.append(_run_passport_tail_restore_case(case_id, max_lines=max_lines))
            continue
        if kind == "first_user_profile":
            results.append(_run_first_user_profile_case(case_id))
            continue
        if kind == "first_recent_doc_binding":
            results.append(_run_first_recent_doc_binding_case(case_id))
            continue
        results.append({"id": case_id, "status": "skipped", "reason": f"unsupported_kind:{kind}"})

    passed = sum(1 for item in results if item.get("status") == "passed")
    failed = sum(1 for item in results if item.get("status") == "failed")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    report = {
        "schema": "ester.restart_continuity.benchmark.v1",
        "ts": int(time.time()),
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": failed,
        "cases_skipped": skipped,
        "results": results,
    }

    base = _bench_dir()
    stem = time.strftime("%Y%m%d_%H%M%S", time.localtime(report["ts"]))
    json_path = os.path.join(base, f"restart_benchmark_{stem}.json")
    latest_path = os.path.join(base, "latest.json")
    history_path = os.path.join(base, "history.jsonl")
    _write_json(json_path, report)
    _write_json(latest_path, report)
    _append_jsonl(history_path, report)
    try:
        from modules.memory import memory_index  # type: ignore

        memory_index.ensure_materialized()
    except Exception:
        pass
    return {"ok": True, "path": json_path, "latest_path": latest_path, "history_path": history_path, "report": report}


__all__ = ["run_restart_benchmark"]
