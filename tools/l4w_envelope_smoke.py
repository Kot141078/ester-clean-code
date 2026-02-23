# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory
from modules.runtime import capability_drift, drift_quarantine, evidence_signing, l4w_witness
from modules.thinking import action_registry


def _read_json(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return dict(raw) if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _write_evidence_packet(persist_dir: Path, agent_id: str, event_id: str, reviewer: str, summary: str) -> Dict[str, str]:
    evidence_root = (persist_dir / "capability_drift" / "evidence").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    file_name = f"{agent_id}_{event_id}_{ts}.json"
    evidence_path = (evidence_root / file_name).resolve()
    packet = {
        "schema": "ester.evidence.v1",
        "created_ts": ts,
        "reviewer": str(reviewer or ""),
        "agent_id": str(agent_id or ""),
        "quarantine_event_id": str(event_id or ""),
        "decision": "CLEAR_QUARANTINE",
        "summary": str(summary or "")[:200],
        "findings": {"smoke": True},
        "artifacts": [],
    }
    sign_rep = evidence_signing.sign_packet(dict(packet))
    signed = dict(sign_rep.get("packet") or packet)
    evidence_path.write_text(json.dumps(signed, ensure_ascii=True, indent=2), encoding="utf-8")
    sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    return {"path": file_name, "sha256": sha256, "full_path": str(evidence_path)}


def _run_json_cmd(args: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    proc = subprocess.run(args, capture_output=True, text=True, env=env)
    out_raw = str(proc.stdout or "").strip()
    payload: Dict[str, Any] = {}
    if out_raw:
        try:
            payload = json.loads(out_raw)
            if not isinstance(payload, dict):
                payload = {"ok": False, "raw_stdout": out_raw}
        except Exception:
            payload = {"ok": False, "raw_stdout": out_raw}
    payload.setdefault("ok", bool(proc.returncode == 0))
    payload["rc"] = int(proc.returncode)
    payload["stderr"] = str(proc.stderr or "")
    return payload


def _build_l4w_with_tool(env: Dict[str, str], *, agent_id: str, event_id: str, evidence: Dict[str, str], reviewer: str, summary: str) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str((ROOT / "tools" / "l4w_build_envelope_for_clear.py").resolve()),
        "--agent-id",
        agent_id,
        "--event-id",
        event_id,
        "--evidence-path",
        str(evidence.get("path") or ""),
        "--evidence-sha256",
        str(evidence.get("sha256") or ""),
        "--reviewer",
        reviewer,
        "--summary",
        summary,
        "--write-disclosure-template",
        "1",
    ]
    return _run_json_cmd(cmd, env)


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_l4w_envelope_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_VOLITION_ALLOWED_HOURS",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
        "ESTER_EVIDENCE_SIG_REQUIRED",
        "ESTER_L4W_REQUIRED",
        "ESTER_L4W_CHAIN_REQUIRED",
        "ESTER_L4W_CHAIN_DISABLED",
        "ESTER_DRIFT_TTL_SEC",
        "ESTER_QUARANTINE_TTL_SEC",
        "ESTER_QUARANTINE_FAIL_MAX",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_EVIDENCE_SIG_REQUIRED"] = "1"
    os.environ["ESTER_L4W_REQUIRED"] = "1"
    os.environ["ESTER_L4W_CHAIN_REQUIRED"] = "1"
    os.environ["ESTER_L4W_CHAIN_DISABLED"] = "0"
    os.environ["ESTER_DRIFT_TTL_SEC"] = "1"
    os.environ["ESTER_QUARANTINE_TTL_SEC"] = "1"
    os.environ["ESTER_QUARANTINE_FAIL_MAX"] = "3"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_l4w_envelope_smoke",
                "goal": "l4w envelope smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.l4w_envelope_smoke",
                "budgets": {"max_actions": 8, "max_work_ms": 3500, "window": 60, "est_work_ms": 300},
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2

        agent_id = str(create.get("agent_id") or "")
        spec_path = Path(str(create.get("spec_path") or "")).resolve()
        if not spec_path.exists():
            print(json.dumps({"ok": False, "error": "spec_missing", "spec_path": str(spec_path)}, ensure_ascii=True, indent=2))
            return 2
        original_spec_bytes = spec_path.read_bytes()

        baseline = capability_drift.scan_agents_for_drift(write=True, max_agents=2000)

        # B) induce HIGH drift quarantine
        spec = _read_json(spec_path)
        tampered_allow = drift_quarantine.normalize_allowlist(list(spec.get("allowed_actions") or []) + ["llm.remote.call"])
        spec["allowed_actions"] = tampered_allow
        spec["allowed_actions_hash"] = capability_drift.allowlist_hash(tampered_allow)
        _write_json(spec_path, spec)
        q_set_1 = drift_quarantine.ensure_quarantine_for_agent(agent_id, source="l4w_smoke_first")
        event_id_1 = str(q_set_1.get("event_id") or "")

        evidence_1 = _write_evidence_packet(
            persist_dir,
            agent_id,
            event_id_1,
            "tools.l4w_envelope_smoke",
            "first clear attempt without l4w must fail",
        )

        # C) clear without l4w -> deny L4W_REQUIRED
        clear_missing_l4w = action_registry.invoke(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id_1,
                "reason": "missing l4w",
                "by": "tools.l4w_envelope_smoke",
                "chain_id": "chain_l4w_missing",
                "evidence": {"path": evidence_1["path"], "sha256": evidence_1["sha256"]},
            },
        )
        state_after_missing = drift_quarantine.is_quarantined(agent_id)

        # E) build envelope via tool
        env_for_subproc = dict(os.environ)
        build_1 = _build_l4w_with_tool(
            env_for_subproc,
            agent_id=agent_id,
            event_id=event_id_1,
            evidence=evidence_1,
            reviewer="tools.l4w_envelope_smoke",
            summary="first clear approved with l4w",
        )
        l4w_1 = {
            "envelope_path": str(build_1.get("envelope_path") or ""),
            "envelope_sha256": str(build_1.get("envelope_sha256") or ""),
        }

        # F) clear with evidence + envelope -> success
        clear_ok_1 = action_registry.invoke(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id_1,
                "reason": "first clear with l4w",
                "by": "tools.l4w_envelope_smoke",
                "chain_id": "chain_l4w_first_ok",
                "evidence": {"path": evidence_1["path"], "sha256": evidence_1["sha256"]},
                "l4w": dict(l4w_1),
            },
        )
        spec_path.write_bytes(original_spec_bytes)

        # G) tamper envelope bytes and clear -> hash/signature fail
        q_set_2 = drift_quarantine.set_manual_quarantine(
            agent_id,
            reason_code="L4W_TAMPER_SMOKE",
            severity="HIGH",
            kind="l4w_tamper_smoke",
            source="tools.l4w_envelope_smoke",
        )
        event_id_2 = str(q_set_2.get("event_id") or "")
        evidence_2 = _write_evidence_packet(
            persist_dir,
            agent_id,
            event_id_2,
            "tools.l4w_envelope_smoke",
            "tampered envelope should fail",
        )
        build_2 = _build_l4w_with_tool(
            env_for_subproc,
            agent_id=agent_id,
            event_id=event_id_2,
            evidence=evidence_2,
            reviewer="tools.l4w_envelope_smoke",
            summary="tampered envelope",
        )
        tampered_rel_path = str(build_2.get("envelope_path") or "")
        tampered_sha_before = str(build_2.get("envelope_sha256") or "")
        tampered_path_rep = l4w_witness.resolve_envelope_path(tampered_rel_path)
        tampered_full_path = Path(str(tampered_path_rep.get("envelope_path") or "")).resolve()
        tampered_bytes = bytearray(tampered_full_path.read_bytes())
        if tampered_bytes:
            tampered_bytes[-1] = 65 if tampered_bytes[-1] != 65 else 66
            tampered_full_path.write_bytes(bytes(tampered_bytes))
        clear_tampered = action_registry.invoke(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id_2,
                "reason": "tampered l4w",
                "by": "tools.l4w_envelope_smoke",
                "chain_id": "chain_l4w_tampered",
                "evidence": {"path": evidence_2["path"], "sha256": evidence_2["sha256"]},
                "l4w": {"envelope_path": tampered_rel_path, "envelope_sha256": tampered_sha_before},
            },
        )

        # H) wrong prev_hash fails, correct prev_hash passes
        q_set_3 = drift_quarantine.set_manual_quarantine(
            agent_id,
            reason_code="L4W_CHAIN_SMOKE",
            severity="HIGH",
            kind="l4w_chain_smoke",
            source="tools.l4w_envelope_smoke",
        )
        event_id_3 = str(q_set_3.get("event_id") or "")
        evidence_3 = _write_evidence_packet(
            persist_dir,
            agent_id,
            event_id_3,
            "tools.l4w_envelope_smoke",
            "chain validation test",
        )
        wrong_prev = "f" * 64
        built_wrong = l4w_witness.build_envelope_for_clear(
            agent_id,
            event_id_3,
            reviewer="tools.l4w_envelope_smoke",
            summary="wrong prev hash",
            notes=None,
            evidence_path=str(evidence_3["path"]),
            evidence_sha256=str(evidence_3["sha256"]),
            evidence_schema="ester.evidence.v1",
            evidence_sig_ok=True,
            evidence_payload_hash="",
            prev_hash=wrong_prev,
            on_time=True,
            late=False,
        )
        signed_wrong = l4w_witness.sign_envelope(dict(built_wrong.get("envelope") or {}))
        written_wrong = l4w_witness.write_envelope(agent_id, dict(signed_wrong.get("envelope") or {}))
        clear_wrong_prev = action_registry.invoke(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id_3,
                "reason": "wrong prev hash",
                "by": "tools.l4w_envelope_smoke",
                "chain_id": "chain_l4w_wrong_prev",
                "evidence": {"path": evidence_3["path"], "sha256": evidence_3["sha256"]},
                "l4w": {
                    "envelope_path": str(written_wrong.get("envelope_rel_path") or ""),
                    "envelope_sha256": str(written_wrong.get("envelope_sha256") or ""),
                },
            },
        )

        build_3 = _build_l4w_with_tool(
            env_for_subproc,
            agent_id=agent_id,
            event_id=event_id_3,
            evidence=evidence_3,
            reviewer="tools.l4w_envelope_smoke",
            summary="correct prev hash",
        )
        clear_ok_3 = action_registry.invoke(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id_3,
                "reason": "correct prev hash",
                "by": "tools.l4w_envelope_smoke",
                "chain_id": "chain_l4w_correct_prev",
                "evidence": {"path": evidence_3["path"], "sha256": evidence_3["sha256"]},
                "l4w": {
                    "envelope_path": str(build_3.get("envelope_path") or ""),
                    "envelope_sha256": str(build_3.get("envelope_sha256") or ""),
                },
            },
        )

        # I) disclosure make + verify_disclosure
        make_disclosure = _run_json_cmd(
            [
                sys.executable,
                "-B",
                str((ROOT / "tools" / "l4w_disclosure_make.py").resolve()),
                "--envelope-path",
                str(build_3.get("envelope_path") or ""),
                "--sign",
                "1",
            ],
            env_for_subproc,
        )
        envelope_rep = l4w_witness.resolve_envelope_path(str(build_3.get("envelope_path") or ""))
        envelope_obj = _read_json(Path(str(envelope_rep.get("envelope_path") or "")).resolve())
        disclosure_obj = _read_json(Path(str(make_disclosure.get("disclosure_path") or "")).resolve())
        disclosure_verify = l4w_witness.verify_disclosure(envelope_obj, disclosure_obj)

        status = drift_quarantine.build_drift_quarantine_status()

        ok = (
            bool(baseline.get("ok"))
            and bool(q_set_1.get("ok"))
            and bool(q_set_1.get("active"))
            and (not bool(clear_missing_l4w.get("ok")))
            and str(clear_missing_l4w.get("error_code") or "") == "L4W_REQUIRED"
            and bool(state_after_missing.get("active"))
            and bool(build_1.get("ok"))
            and bool(clear_ok_1.get("ok"))
            and bool(clear_ok_1.get("cleared"))
            and str(clear_ok_1.get("l4w_envelope_hash") or "")
            and bool(q_set_2.get("ok"))
            and (not bool(clear_tampered.get("ok")))
            and str(clear_tampered.get("error_code") or "") in {"L4W_HASH_MISMATCH", "L4W_SIG_INVALID"}
            and bool(q_set_3.get("ok"))
            and (not bool(clear_wrong_prev.get("ok")))
            and str(clear_wrong_prev.get("error_code") or "") == "L4W_CHAIN_BROKEN"
            and bool(build_3.get("ok"))
            and bool(clear_ok_3.get("ok"))
            and bool(clear_ok_3.get("cleared"))
            and bool(make_disclosure.get("ok"))
            and bool(disclosure_verify.get("ok"))
            and bool((dict(disclosure_verify.get("which_paths_ok") or {})).get("claim.reviewer"))
            and bool((dict(disclosure_verify.get("which_paths_ok") or {})).get("claim.summary"))
            and isinstance(status.get("l4w"), dict)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "baseline": baseline,
            "q_set_1": q_set_1,
            "evidence_1": evidence_1,
            "clear_missing_l4w": clear_missing_l4w,
            "state_after_missing": state_after_missing,
            "build_1": build_1,
            "clear_ok_1": clear_ok_1,
            "q_set_2": q_set_2,
            "evidence_2": evidence_2,
            "build_2": build_2,
            "clear_tampered": clear_tampered,
            "q_set_3": q_set_3,
            "evidence_3": evidence_3,
            "written_wrong": written_wrong,
            "clear_wrong_prev": clear_wrong_prev,
            "build_3": build_3,
            "clear_ok_3": clear_ok_3,
            "make_disclosure": make_disclosure,
            "disclosure_verify": disclosure_verify,
            "status_l4w": status.get("l4w"),
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
