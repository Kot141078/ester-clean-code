# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]


def _run_smoke(script_rel: str, env: Dict[str, str]) -> Dict[str, Any]:
    script_path = (ROOT / script_rel).resolve()
    cmd = [sys.executable, "-B", str(script_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    payload: Dict[str, Any] = {}
    stdout_raw = str(proc.stdout or "").strip()
    if stdout_raw:
        try:
            obj = json.loads(stdout_raw)
            if isinstance(obj, dict):
                payload = dict(obj)
        except Exception:
            payload = {}
    return {
        "script": script_rel,
        "cmd": cmd,
        "rc": int(proc.returncode),
        "ok": bool(payload.get("ok")) if isinstance(payload, dict) else False,
        "payload": payload,
        "stderr": str(proc.stderr or ""),
    }


def _scenario_a(rep_spec: Dict[str, Any], rep_clear_req: Dict[str, Any]) -> Dict[str, Any]:
    p_spec = dict(rep_spec.get("payload") or {})
    p_clear = dict(rep_clear_req.get("payload") or {})
    spec_tamper_code = str(dict(p_spec.get("enqueue_tamper") or {}).get("error_code") or "")
    clear_missing_code = str(dict(p_clear.get("clear_missing") or {}).get("error_code") or "")
    ok = (
        int(rep_spec.get("rc") or 0) == 0
        and bool(rep_spec.get("ok"))
        and spec_tamper_code == "SPEC_TAMPER_NO_JOURNAL"
        and bool(dict(p_spec.get("clear_rep") or {}).get("ok"))
        and bool(dict(p_spec.get("enqueue_after") or {}).get("ok"))
        and int(rep_clear_req.get("rc") or 0) == 0
        and bool(rep_clear_req.get("ok"))
        and clear_missing_code == "EVIDENCE_REQUIRED"
        and bool(dict(p_clear.get("clear_ok") or {}).get("ok"))
    )
    return {
        "name": "scenario_a_capability_escalation",
        "ok": ok,
        "checks": {
            "spec_guard_tamper_deny": spec_tamper_code,
            "clear_requires_evidence": clear_missing_code,
            "clear_with_evidence_ok": bool(dict(p_clear.get("clear_ok") or {}).get("ok")),
            "after_restore_enqueue_ok": bool(dict(p_spec.get("enqueue_after") or {}).get("ok")),
        },
        "steps": [rep_spec, rep_clear_req],
    }


def _scenario_b(rep_drift: Dict[str, Any], rep_quarantine: Dict[str, Any]) -> Dict[str, Any]:
    p_drift = dict(rep_drift.get("payload") or {})
    p_quar = dict(rep_quarantine.get("payload") or {})
    block_code = str(dict(p_quar.get("enqueue_block") or {}).get("error_code") or "")
    ok = (
        int(rep_drift.get("rc") or 0) == 0
        and bool(rep_drift.get("ok"))
        and bool(p_drift.get("has_tamper"))
        and int(rep_quarantine.get("rc") or 0) == 0
        and bool(rep_quarantine.get("ok"))
        and block_code == "DRIFT_QUARANTINED"
        and bool(dict(p_quar.get("clear_rep") or {}).get("ok"))
        and bool(dict(p_quar.get("enqueue_after") or {}).get("ok"))
    )
    return {
        "name": "scenario_b_allowlist_tamper_drift",
        "ok": ok,
        "checks": {
            "drift_detected": bool(p_drift.get("has_tamper")),
            "quarantine_block_code": block_code,
            "clear_with_evidence_ok": bool(dict(p_quar.get("clear_rep") or {}).get("ok")),
        },
        "steps": [rep_drift, rep_quarantine],
    }


def _scenario_c(rep_roster: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(rep_roster.get("payload") or {})
    checks = dict(p.get("checks") or {})
    verify_tampered = dict(p.get("verify_tampered") or {})
    tamper_fail = bool(checks.get("tamper_fail")) or int(verify_tampered.get("rc") or 0) == 2
    ok = int(rep_roster.get("rc") or 0) == 0 and bool(rep_roster.get("ok")) and tamper_fail
    return {
        "name": "scenario_c_roster_log_forgery",
        "ok": ok,
        "checks": {
            "tamper_fail": tamper_fail,
            "verify_tampered_rc": int(verify_tampered.get("rc") or 0),
        },
        "steps": [rep_roster],
    }


def _scenario_d(rep_bundle: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(rep_bundle.get("payload") or {})
    verify_tree_tampered = dict(p.get("verify_tree_tampered") or {})
    verify_sig_tampered = dict(p.get("verify_sig_tampered") or {})
    tamper_fail = int(verify_tree_tampered.get("rc") or 0) == 2 and int(verify_sig_tampered.get("rc") or 0) == 2
    ok = int(rep_bundle.get("rc") or 0) == 0 and bool(rep_bundle.get("ok")) and tamper_fail
    return {
        "name": "scenario_d_bundle_tamper",
        "ok": ok,
        "checks": {
            "tree_tamper_fail_rc": int(verify_tree_tampered.get("rc") or 0),
            "sig_tamper_fail_rc": int(verify_sig_tampered.get("rc") or 0),
        },
        "steps": [rep_bundle],
    }


def main() -> int:
    env = dict(os.environ)
    env["ESTER_OFFLINE"] = "1"
    env["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"

    rep_spec_guard = _run_smoke("tools/spec_guard_smoke.py", env)
    rep_clear_requires = _run_smoke("tools/quarantine_clear_requires_evidence_smoke.py", env)
    rep_cap_drift = _run_smoke("tools/capability_drift_smoke.py", env)
    rep_drift_quar = _run_smoke("tools/drift_quarantine_smoke.py", env)
    rep_roster = _run_smoke("tools/roster_transparency_log_smoke.py", env)
    rep_bundle = _run_smoke("tools/l4w_bundle_signing_smoke.py", env)

    subtests = [
        _scenario_a(rep_spec_guard, rep_clear_requires),
        _scenario_b(rep_cap_drift, rep_drift_quar),
        _scenario_c(rep_roster),
        _scenario_d(rep_bundle),
    ]
    ok = all(bool(x.get("ok")) for x in subtests)

    out = {
        "ok": ok,
        "offline": True,
        "subtests_total": len(subtests),
        "subtests_passed": sum(1 for x in subtests if bool(x.get("ok"))),
        "subtests": subtests,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

