# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

from modules.memory.active_context import build_active_memory_bundle


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _default_corpus_path() -> str:
    return os.path.join(_state_root(), "config", "recall_benchmark_corpus.json")


def _bench_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "recall", "benchmarks")


def _load_corpus(path: Optional[str] = None) -> List[Dict[str, Any]]:
    corpus_path = str(path or _default_corpus_path()).strip()
    if not corpus_path or not os.path.exists(corpus_path):
        return []
    try:
        with open(corpus_path, "r", encoding="utf-8") as f:
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


def run_benchmark(cases: Optional[Iterable[Dict[str, Any]]] = None, *, corpus_path: Optional[str] = None) -> Dict[str, Any]:
    corpus = [dict(item) for item in (cases or _load_corpus(corpus_path))]
    results: List[Dict[str, Any]] = []

    for case in corpus:
        bundle = build_active_memory_bundle(
            user_text=str(case.get("query") or ""),
            evidence_memory=str(case.get("evidence_memory") or ""),
            user_facts=list(case.get("user_facts") or []),
            recent_entries=list(case.get("recent_entries") or []),
            profile_context=str(case.get("profile_context") or ""),
            recent_doc_context=str(case.get("recent_doc_context") or ""),
            people_context=str(case.get("people_context") or ""),
            daily_report=str(case.get("daily_report") or ""),
        )
        context = str(bundle.get("context") or "")
        required_sections = [str(x) for x in list(case.get("required_sections") or []) if str(x).strip()]
        required_substrings = [str(x) for x in list(case.get("required_substrings") or []) if str(x).strip()]
        missing_sections = [item for item in required_sections if item not in context]
        missing_substrings = [item for item in required_substrings if item not in context]
        ok = (not missing_sections) and (not missing_substrings)
        results.append(
            {
                "id": str(case.get("id") or ""),
                "ok": ok,
                "missing_sections": missing_sections,
                "missing_substrings": missing_substrings,
                "stats": dict(bundle.get("stats") or {}),
            }
        )

    passed = sum(1 for item in results if item.get("ok"))
    report = {
        "schema": "ester.recall.benchmark.v1",
        "ts": int(time.time()),
        "cases_total": len(results),
        "cases_passed": passed,
        "cases_failed": max(0, len(results) - passed),
        "results": results,
    }
    base = _bench_dir()
    stem = time.strftime("%Y%m%d_%H%M%S", time.localtime(report["ts"]))
    json_path = os.path.join(base, f"benchmark_{stem}.json")
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


__all__ = ["run_benchmark"]
