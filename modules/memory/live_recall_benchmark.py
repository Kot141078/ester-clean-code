# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.memory.active_context import build_active_memory_bundle
from modules.memory.profile_snapshot import (
    list_known_user_ids,
    load_profile_snapshot,
    render_profile_context,
)
from modules.memory.recent_docs import get_last_resolved_document, list_recent_docs
from modules.memory.user_facts_store import load_user_facts
from modules.rag.retrieval_router import _is_internal_flashback_record, retrieve

try:
    from modules.memory import store as memory_store  # type: ignore
except Exception:
    memory_store = None  # type: ignore


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _default_cases_path() -> str:
    return os.path.join(_state_root(), "config", "live_recall_benchmark_cases.json")


def _bench_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "recall", "live")


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


def _collect_recent_entries(
    *,
    chat_id: Optional[int],
    user_id: Optional[int],
    days: int = 14,
    topk: int = 6,
    include_global: bool = False,
) -> List[Dict[str, Any]]:
    if memory_store is None:
        return []
    cutoff = int(time.time()) - (max(1, int(days)) * 86400)
    rows = []
    try:
        rows = list(getattr(memory_store, "_MEM", {}).values())
    except Exception:
        rows = []

    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            if _is_internal_flashback_record(row):
                continue
        except Exception:
            pass
        try:
            ts = int(row.get("ts") or 0)
        except Exception:
            ts = 0
        if ts and ts < cutoff:
            continue
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        row_chat = str(meta.get("chat_id") or "").strip()
        row_user = str(meta.get("user_id") or "").strip()
        if chat_id is not None and row_chat not in ("", str(chat_id)):
            continue
        if user_id is not None and row_user not in ("", str(user_id)):
            continue
        if not include_global and (row_chat == "" and row_user == ""):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        out.append(
            {
                "ts": ts,
                "text": text,
                "type": str(row.get("type") or row.get("kind") or ""),
                "meta": meta,
            }
        )

    out.sort(key=lambda item: int(item.get("ts") or 0), reverse=True)
    seen = set()
    uniq: List[Dict[str, Any]] = []
    for row in out:
        text = str(row.get("text") or "").strip()
        if text in seen:
            continue
        seen.add(text)
        uniq.append(row)
        if len(uniq) >= max(1, int(topk)):
            break
    return uniq


def _resolve_first_user_case() -> Optional[Dict[str, Any]]:
    for user_id in list_known_user_ids(limit=50):
        facts = list(load_user_facts(user_id, include_legacy=False) or [])
        snapshot = load_profile_snapshot(user_id)
        if facts:
            return {
                "user_id": user_id,
                "chat_id": str(snapshot.get("last_chat_id") or ""),
                "display_name": str(snapshot.get("display_name") or ""),
                "facts": facts,
                "profile": snapshot,
            }
    return None


def _recent_doc_candidates() -> List[Tuple[int, Dict[str, Any]]]:
    path = os.path.join(_state_root(), "data", "memory", "recent_chat_docs.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        return []
    out: List[Tuple[int, Dict[str, Any]]] = []
    by_chat = data.get("by_chat") if isinstance(data, dict) else {}
    if not isinstance(by_chat, dict):
        return []
    for key, entries in by_chat.items():
        try:
            chat_id = int(str(key))
        except Exception:
            continue
        if not isinstance(entries, list) or not entries:
            continue
        first = next((dict(item) for item in entries if isinstance(item, dict)), None)
        if first:
            out.append((chat_id, first))
    return out


def _resolve_first_recent_doc_case() -> Optional[Dict[str, Any]]:
    for chat_id, entry in _recent_doc_candidates():
        binding = get_last_resolved_document(chat_id, None) or {}
        name = str(entry.get("name") or binding.get("orig_name") or binding.get("title") or "").strip()
        if not name:
            continue
        return {
            "chat_id": str(chat_id),
            "user_id": "",
            "name": name,
            "entry": entry,
            "binding": binding,
        }
    return None


def _build_live_bundle(query: str, *, user_id: Optional[str], chat_id: Optional[str]) -> Dict[str, Any]:
    uid = int(user_id) if str(user_id or "").strip().isdigit() else None
    cid = int(chat_id) if str(chat_id or "").strip().isdigit() else None
    facts = list(load_user_facts(user_id, include_legacy=False) or []) if str(user_id or "").strip() else []
    snapshot = load_profile_snapshot(user_id) if str(user_id or "").strip() else {}
    profile_context = render_profile_context(snapshot)
    retrieval = retrieve(query, chat_id=cid, user_id=uid)
    recent_entries = _collect_recent_entries(chat_id=cid, user_id=uid, include_global=False)
    bundle = build_active_memory_bundle(
        user_text=query,
        evidence_memory=str(retrieval.get("context") or ""),
        user_facts=facts,
        recent_entries=recent_entries,
        profile_context=profile_context,
    )
    return {
        "bundle": bundle,
        "profile": snapshot,
        "facts": facts,
        "retrieval": retrieval,
        "recent_entries": recent_entries,
    }


def _run_first_user_fact_case(case_id: str) -> Dict[str, Any]:
    resolved = _resolve_first_user_case()
    if not resolved:
        return {"id": case_id, "status": "skipped", "reason": "no_user_with_facts"}
    user_id = str(resolved.get("user_id") or "")
    chat_id = str(resolved.get("chat_id") or "")
    query = "Что ты про меня помнишь?"
    live = _build_live_bundle(query, user_id=user_id, chat_id=chat_id)
    context = str((live.get("bundle") or {}).get("context") or "")
    first_fact = str((resolved.get("facts") or [""])[0] or "").strip()
    missing = []
    if "[ACTIVE_USER_FACTS]" not in context:
        missing.append("[ACTIVE_USER_FACTS]")
    if first_fact and first_fact not in context:
        missing.append(first_fact)
    return {
        "id": case_id,
        "status": "passed" if not missing else "failed",
        "query": query,
        "user_id": user_id,
        "chat_id": chat_id,
        "expected_fact": first_fact,
        "missing": missing,
        "stats": dict((live.get("bundle") or {}).get("stats") or {}),
    }


def _run_first_recent_doc_case(case_id: str) -> Dict[str, Any]:
    resolved = _resolve_first_recent_doc_case()
    if not resolved:
        return {"id": case_id, "status": "skipped", "reason": "no_recent_doc_binding"}
    user_id = str(resolved.get("user_id") or "")
    chat_id = str(resolved.get("chat_id") or "")
    name = str(resolved.get("name") or "").strip()
    query = f"что в файле {name}"
    live = _build_live_bundle(query, user_id=user_id, chat_id=chat_id)
    retrieval = dict(live.get("retrieval") or {})
    context = str((live.get("bundle") or {}).get("context") or "")
    missing = []
    if name and name not in context:
        missing.append(name)
    if not bool((retrieval.get("stats") or {}).get("resolved_doc")):
        missing.append("resolved_doc")
    return {
        "id": case_id,
        "status": "passed" if not missing else "failed",
        "query": query,
        "user_id": user_id,
        "chat_id": chat_id,
        "doc_name": name,
        "missing": missing,
        "stats": dict((live.get("bundle") or {}).get("stats") or {}),
        "retrieval_stats": dict(retrieval.get("stats") or {}),
    }


def run_live_benchmark(cases: Optional[Iterable[Dict[str, Any]]] = None, *, cases_path: Optional[str] = None) -> Dict[str, Any]:
    corpus = [dict(item) for item in (cases or _load_cases(cases_path))]
    if not corpus:
        corpus = [
            {"id": "live_first_user_fact", "kind": "first_user_fact"},
            {"id": "live_first_recent_doc", "kind": "first_recent_doc"},
        ]

    results: List[Dict[str, Any]] = []
    for case in corpus:
        kind = str(case.get("kind") or "").strip().lower()
        case_id = str(case.get("id") or kind or f"case_{len(results)+1}")
        if kind == "first_user_fact":
            results.append(_run_first_user_fact_case(case_id))
            continue
        if kind == "first_recent_doc":
            results.append(_run_first_recent_doc_case(case_id))
            continue
        results.append({"id": case_id, "status": "skipped", "reason": f"unsupported_kind:{kind}"})

    passed = sum(1 for item in results if item.get("status") == "passed")
    failed = sum(1 for item in results if item.get("status") == "failed")
    skipped = sum(1 for item in results if item.get("status") == "skipped")
    report = {
        "schema": "ester.live_recall.benchmark.v1",
        "ts": int(time.time()),
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": failed,
        "cases_skipped": skipped,
        "results": results,
    }

    base = _bench_dir()
    stem = time.strftime("%Y%m%d_%H%M%S", time.localtime(report["ts"]))
    json_path = os.path.join(base, f"live_benchmark_{stem}.json")
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


__all__ = ["run_live_benchmark"]
