# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


CheckFn = Callable[[], Dict[str, Any]]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _smoke_journal() -> Dict[str, Any]:
    from modules.memory import journal

    rec = journal.record_event(
        "iter34",
        "smoke",
        result="ok",
        source="iter34_smoke",
        trace_id="iter34-smoke",
    )
    tail = journal.read_tail(5)
    _assert(isinstance(rec, dict), "journal.record_event must return dict")
    _assert(isinstance(tail, list) and bool(tail), "journal.read_tail must return non-empty list")
    row = dict(tail[-1])
    for key in ("ts", "kind", "source", "payload", "ok", "error"):
        _assert(key in row, f"journal tail row missing key: {key}")
    return {"event_id": str(rec.get("id") or ""), "tail_len": len(tail)}


def _smoke_passport() -> Dict[str, Any]:
    from modules.mem import passport

    prompt = passport.get_identity_system_prompt(max_chars=220)
    status = passport.runtime_status() if hasattr(passport, "runtime_status") else {}
    _assert(isinstance(prompt, str) and len(prompt) > 0, "passport prompt must be non-empty")
    _assert(isinstance(status, dict), "passport.runtime_status must return dict")
    _assert("readonly" in status, "passport.runtime_status must expose readonly flag")
    return {"readonly": bool(status.get("readonly")), "warnings": len(status.get("warnings") or [])}


def _smoke_caution_guard() -> Dict[str, Any]:
    from flask import Flask
    from modules.middleware import caution_guard

    app = Flask("iter34_smoke")
    caution_guard.register(app)

    @app.get("/debug/iter34/fail")
    def _debug_fail() -> Any:
        raise RuntimeError("iter34 smoke failure")

    with app.test_client() as client:
        resp = client.get("/debug/iter34/fail")
        data = resp.get_json(silent=True) or {}
    _assert(int(resp.status_code) == 500, "caution_guard debug error should return 500")
    _assert(data.get("ok") is False, "caution_guard debug error payload must set ok=false")
    _assert(str(data.get("error") or "") == "debug_endpoint_failed", "unexpected caution_guard error code")
    _assert(bool(resp.headers.get("X-Request-Id")), "caution_guard must attach X-Request-Id")
    return {"status": int(resp.status_code)}


def _smoke_beacons_status() -> Dict[str, Any]:
    from modules import kg_beacons_query

    st = kg_beacons_query.status()
    for key in ("ok", "beacons_enabled", "store_path", "beacons_count", "last_update_ts", "last_error"):
        _assert(key in st, f"kg_beacons_query.status missing key: {key}")
    return {"ok": bool(st.get("ok")), "count": int(st.get("beacons_count") or 0)}


def _smoke_scheduler_load() -> Dict[str, Any]:
    from modules.cron import scheduler

    jobs = scheduler._load()
    _assert(isinstance(jobs, list), "cron.scheduler._load must return list")
    return {"jobs": int(len(jobs))}


def _smoke_backpressure_counters() -> Dict[str, Any]:
    from modules.ingest import backpressure

    rep = backpressure.counters()
    for key in ("ok", "ingest_queue", "bytes_pending", "last_ingest_ts", "drops"):
        _assert(key in rep, f"backpressure.counters missing key: {key}")
    _assert(isinstance(rep.get("ingest_queue"), int), "ingest_queue must be int")
    _assert(isinstance(rep.get("bytes_pending"), int), "bytes_pending must be int")
    return {"queue": int(rep.get("ingest_queue") or 0), "drops": int(rep.get("drops") or 0)}


def _smoke_autolink() -> Dict[str, Any]:
    from modules.kg import autolink

    rep = autolink.autolink(
        [{"id": "iter34-doc", "text": "Ester met the owner in DefaultCity. #agents"}],
        mode="simple",
        link_to_rag=True,
    )
    _assert(bool(rep.get("ok")), "autolink must return ok=true")
    _assert(isinstance(rep.get("links"), list), "autolink must return links list")
    _assert(isinstance(rep.get("rag_hints"), list), "autolink must return rag_hints list")
    return {"links": len(rep.get("links") or []), "nodes": len(rep.get("nodes") or [])}


def _smoke_autonomy_plan() -> Dict[str, Any]:
    from modules.self import autonomy

    rep = autonomy.plan(
        "review offline quality checks",
        budget={"max_work_ms": 400, "max_actions": 3},
        targets=["local"],
    )
    for key in ("ok", "plan", "template", "needs_oracle", "reason"):
        _assert(key in rep, f"autonomy.plan missing key: {key}")
    _assert(isinstance(rep.get("plan"), dict), "autonomy.plan.plan must be dict")
    _assert(isinstance(rep.get("template"), dict), "autonomy.plan.template must be dict")
    return {"reason": str(rep.get("reason") or ""), "needs_oracle": bool(rep.get("needs_oracle"))}


def _smoke_provider_fallback() -> Dict[str, Any]:
    from modules import providers

    messages = [{"role": "user", "content": "iter34 provider fallback"}]
    chat = providers.send_chat(messages, provider="__missing_provider__")
    _assert(bool(chat.get("ok")), "providers.send_chat fallback should return ok=true")
    _assert(bool(chat.get("text")), "providers.send_chat fallback should return text")

    emb1 = providers.send_embeddings(["iter34 provider fallback"], provider="__missing_provider__", dim=16)
    emb2 = providers.send_embeddings(["iter34 provider fallback"], provider="__missing_provider__", dim=16)
    vec1 = (((emb1 or {}).get("data") or [{}])[0]).get("embedding")
    vec2 = (((emb2 or {}).get("data") or [{}])[0]).get("embedding")
    _assert(isinstance(vec1, list) and bool(vec1), "providers.send_embeddings fallback vector missing")
    _assert(vec1 == vec2, "providers.send_embeddings fallback must be deterministic")
    return {"embedding_dim": len(vec1)}


def main() -> int:
    checks: List[Tuple[str, CheckFn]] = [
        ("journal_record_event", _smoke_journal),
        ("passport_fallback", _smoke_passport),
        ("caution_guard_register", _smoke_caution_guard),
        ("kg_beacons_status", _smoke_beacons_status),
        ("cron_load", _smoke_scheduler_load),
        ("backpressure_counters", _smoke_backpressure_counters),
        ("kg_autolink", _smoke_autolink),
        ("autonomy_plan", _smoke_autonomy_plan),
        ("providers_fallback", _smoke_provider_fallback),
    ]

    failed = 0
    for name, fn in checks:
        try:
            detail = fn()
            print(f"[OK] {name}: {json.dumps(detail, ensure_ascii=False)}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {name}: {e}")
            traceback.print_exc()

    if failed:
        print(f"ITER34_SMOKE_FAIL failed={failed}")
        return 2

    print("ITER34_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
