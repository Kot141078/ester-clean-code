# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _run_check(name: str, fn: Callable[[], Any], failures: List[Dict[str, Any]]) -> None:
    try:
        fn()
    except Exception as exc:
        failures.append({"check": name, "error": f"{exc.__class__.__name__}: {exc}"})


def _check_base_adapter() -> None:
    from modules.judge.adapters import BaseAdapter

    try:
        BaseAdapter().evaluate({}, {})
    except RuntimeError as exc:
        if "adapter_not_configured" in str(exc):
            return
        raise
    raise AssertionError("BaseAdapter.evaluate must raise explicit runtime error")


def _check_watchers_tick() -> None:
    from modules.media import watchers

    out = watchers.tick(limit=0, reason="iter35_smoke")
    if not isinstance(out, dict) or not out.get("ok"):
        raise AssertionError("watchers.tick failed")
    if "queued" not in out:
        raise AssertionError("watchers.tick missing queued")


def _check_device_adapter() -> None:
    from modules.synergy.devices.base import DeviceAdapter

    ad = DeviceAdapter()
    if not ad.can_handle("acme", {"vendor": "acme"}):
        raise AssertionError("DeviceAdapter.can_handle mismatch")
    out = ad.to_canonical("acme", {"latency": 10, "payload": 200}, {})
    for key in ("latency_ms", "flight_time_min", "payload_g"):
        if key not in out:
            raise AssertionError(f"DeviceAdapter.to_canonical missing {key}")


def _check_avatar_make() -> None:
    from modules.social import avatar

    out = avatar.make("iter35_smoke", ["hello"], {"kind": "fallback"}, {"engine": "auto"}, consent=True)
    if not isinstance(out, dict) or "ok" not in out:
        raise AssertionError("avatar.make invalid response")


def _check_tts_engine_try() -> None:
    from modules.studio import tts

    wav = Path("data/studio/tmp") / f"iter35_smoke_{int(time.time())}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    engine = tts._engine_try("iter35 smoke", None, str(wav))
    if engine not in {"edge-tts", "coqui-tts", "espeak", "pyttsx3", "tone", "none"}:
        raise AssertionError(f"Unexpected engine: {engine}")


def _check_export_collect() -> None:
    from modules.reports import export_http

    items = export_http._collect()
    if "manifest.json" not in items:
        raise AssertionError("manifest.json missing")


def _check_act_fallback() -> None:
    import importlib
    import modules.act as act

    act._install_run_plan_fallback()
    runner = importlib.import_module("modules.act.runner")
    out = runner.run_plan({"name": "iter35"})
    if out is None:
        raise AssertionError("runner.run_plan returned None")


def _check_jobs_score() -> None:
    from modules.garage import jobs

    jid = f"iter35-job-{int(time.time())}"
    imp = jobs.job_import(
        {
            "id": jid,
            "title": "Python Flask AI RAG task",
            "body": "Need python flask ai rag ml integration",
            "tags": ["python", "flask", "ai", "rag"],
            "source": "iter35_smoke",
        }
    )
    if not imp.get("ok"):
        raise AssertionError(f"job_import failed: {imp}")
    sc = jobs.job_score(jid)
    if not sc.get("ok"):
        raise AssertionError(f"job_score failed: {sc}")


def _check_sepa_pain001() -> None:
    from modules.finance import sepa

    xml = sepa._pain001(
        debtor={"name": "Ester", "iban": "DE89370400440532013000", "bic": "DEUTDEFF"},
        creditors=[{"name": "Vendor", "iban": "DE89370400440532013000", "bic": "DEUTDEFF", "amount": "1.23"}],
        currency="EUR",
        purpose="iter35 smoke",
        end_to_end="ITER35",
    )
    if not isinstance(xml, (bytes, bytearray)) or not bytes(xml).startswith(b"<?xml"):
        raise AssertionError("sepa._pain001 did not produce xml")


def _check_ingest_guard_import() -> None:
    from modules.ingest import guard

    cfg = guard.get_config()
    if not cfg.get("ok"):
        raise AssertionError("ingest.guard get_config failed")


def _check_macro_error_class() -> None:
    from modules.thinking.rpa_macros import MacroError

    err = MacroError("iter35")
    if not isinstance(err, RuntimeError):
        raise AssertionError("MacroError type mismatch")


def _check_thinker_b() -> None:
    from modules.thinking.think_core import _ThinkerB

    out = _ThinkerB().think("iter35 smoke", {})
    if not isinstance(out, dict) or not out.get("ok"):
        raise AssertionError("ThinkerB think failed")
    if out.get("ab") != "B":
        raise AssertionError("ThinkerB must tag ab=B")


def _check_proposal_wave() -> None:
    from modules.garage import jobs, proposal

    jid = f"iter35-proposal-{int(time.time())}"
    imp = jobs.job_import(
        {
            "id": jid,
            "title": "Python Flask AI RAG video integration",
            "body": "Build flask service with ai rag and video pipeline",
            "tags": ["python", "flask", "ai", "rag", "video", "tts"],
            "source": "iter35_smoke",
        }
    )
    if not imp.get("ok"):
        raise AssertionError(f"proposal wave job_import failed: {imp}")
    built = proposal.proposal_build(jid, client="Iter35", budget=500.0, currency="EUR")
    if not built.get("ok") or not built.get("results"):
        raise AssertionError(f"proposal_build failed: {built}")
    md_path = built["results"][0]["path"]
    pdf_path = proposal.generate_pdf(md_path)
    if not Path(pdf_path).is_file():
        raise AssertionError("generate_pdf did not produce a file")
    assigned = proposal.auto_assign(jid)
    if not assigned.get("ok"):
        raise AssertionError(f"auto_assign failed: {assigned}")


def _check_proactive_classify() -> None:
    from modules.memory import proactive_adapter

    kind = proactive_adapter._classify_record({"type": "todo"})
    if kind != "goal":
        raise AssertionError(f"_classify_record unexpected kind: {kind}")


def _check_loop_basic_create_app() -> None:
    from modules.thinking import loop_basic

    app = loop_basic.create_app()
    cli = app.test_client()
    resp = cli.get("/.well-known/appspecific/com.chrome.devtools.json")
    if resp.status_code != 200:
        raise AssertionError(f"devtools endpoint status={resp.status_code}")
    payload = json.loads(resp.data.decode("utf-8"))
    if not payload.get("ok"):
        raise AssertionError("devtools payload not ok")


def main() -> int:
    os.environ.setdefault("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
    failures: List[Dict[str, Any]] = []
    checks = [
        ("judge.BaseAdapter.evaluate", _check_base_adapter),
        ("media.watchers.tick", _check_watchers_tick),
        ("synergy.DeviceAdapter", _check_device_adapter),
        ("social.avatar.make", _check_avatar_make),
        ("studio.tts._engine_try", _check_tts_engine_try),
        ("reports.export_http._collect", _check_export_collect),
        ("act._install_run_plan_fallback", _check_act_fallback),
        ("garage.jobs.job_score", _check_jobs_score),
        ("finance.sepa._pain001", _check_sepa_pain001),
        ("ingest.guard.__module__", _check_ingest_guard_import),
        ("thinking.rpa_macros.MacroError", _check_macro_error_class),
        ("thinking.think_core._ThinkerB", _check_thinker_b),
        ("garage.proposal wave", _check_proposal_wave),
        ("memory.proactive_adapter._classify_record", _check_proactive_classify),
        ("thinking.loop_basic.create_app", _check_loop_basic_create_app),
    ]

    for name, fn in checks:
        _run_check(name, fn, failures)

    out = {"ok": not failures, "checks": len(checks), "failed": len(failures), "failures": failures}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
