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

from modules.runtime import evidence_signing, l4w_witness


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row or {}), ensure_ascii=True, separators=(",", ":")) + "\n")


def _run_cli(agent_id: str, profile: str, persist_dir: Path, env: Dict[str, str]) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str((ROOT / "tools" / "auditor_verify_l4w.py").resolve()),
        "--agent-id",
        str(agent_id),
        "--profile",
        str(profile),
        "--json",
        "--persist-dir",
        str(persist_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out_raw = str(proc.stdout or "").strip()
    payload: Dict[str, Any] = {}
    if out_raw:
        try:
            payload = json.loads(out_raw)
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
    payload["rc"] = int(proc.returncode)
    payload["stderr"] = str(proc.stderr or "")
    payload.setdefault("ok", bool(proc.returncode == 0))
    payload["errors"] = list(payload.get("errors") or [])
    return payload


def _error_codes(rep: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for row in list(rep.get("errors") or []):
        if isinstance(row, dict):
            code = str(row.get("code") or "").strip()
            if code:
                out.append(code)
    return out


def _make_record(persist_dir: Path, agent_id: str, event_id: str, reviewer: str, summary: str) -> Dict[str, Any]:
    evidence_root = (persist_dir / "capability_drift" / "evidence").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    evidence_rel = f"{agent_id}_{event_id}_{ts}.json"
    evidence_path = (evidence_root / evidence_rel).resolve()

    packet = {
        "schema": "ester.evidence.v1",
        "created_ts": ts,
        "reviewer": reviewer,
        "agent_id": agent_id,
        "quarantine_event_id": event_id,
        "decision": "CLEAR_QUARANTINE",
        "summary": summary,
        "findings": {"smoke": True},
        "artifacts": [],
    }
    signed = evidence_signing.sign_packet(dict(packet))
    if not bool(signed.get("ok")):
        return {"ok": False, "stage": "sign_packet", "details": signed}
    packet_signed = dict(signed.get("packet") or {})
    _write_json(evidence_path, packet_signed)
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()

    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    build = l4w_witness.build_envelope_for_clear(
        agent_id,
        event_id,
        reviewer=reviewer,
        summary=summary,
        notes=None,
        evidence_path=evidence_rel,
        evidence_sha256=evidence_sha,
        evidence_schema="ester.evidence.v1",
        evidence_sig_ok=True,
        evidence_payload_hash=str(signed.get("payload_hash") or ""),
        prev_hash=prev_hash,
        on_time=True,
        late=False,
    )
    if not bool(build.get("ok")):
        return {"ok": False, "stage": "build_envelope", "details": build}
    sign_env = l4w_witness.sign_envelope(dict(build.get("envelope") or {}))
    if not bool(sign_env.get("ok")):
        return {"ok": False, "stage": "sign_envelope", "details": sign_env}
    write_env = l4w_witness.write_envelope(agent_id, dict(sign_env.get("envelope") or {}))
    if not bool(write_env.get("ok")):
        return {"ok": False, "stage": "write_envelope", "details": write_env}
    append = l4w_witness.append_chain_record(
        agent_id,
        quarantine_event_id=event_id,
        envelope_id=str((dict(sign_env.get("envelope") or {})).get("envelope_id") or ""),
        envelope_hash=str(sign_env.get("envelope_hash") or ""),
        prev_hash=prev_hash,
        envelope_path=str(write_env.get("envelope_rel_path") or ""),
        envelope_sha256=str(write_env.get("envelope_sha256") or ""),
        ts=int((dict(sign_env.get("envelope") or {})).get("ts") or ts),
    )
    if not bool(append.get("ok")):
        return {"ok": False, "stage": "append_chain", "details": append}

    disclosure = l4w_witness.build_disclosure(
        str(sign_env.get("envelope_hash") or ""),
        list((dict(build.get("disclosure_template") or {})).get("reveals") or []),
        sign=True,
    )
    write_dis = l4w_witness.write_disclosure(disclosure)
    if not bool(write_dis.get("ok")):
        return {"ok": False, "stage": "write_disclosure", "details": write_dis}

    return {
        "ok": True,
        "ts": int((dict(sign_env.get("envelope") or {})).get("ts") or ts),
        "event_id": event_id,
        "evidence_rel": evidence_rel,
        "evidence_path": str(evidence_path),
        "evidence_sha256": evidence_sha,
        "envelope_rel": str(write_env.get("envelope_rel_path") or ""),
        "envelope_path": str(write_env.get("envelope_path") or ""),
        "envelope_sha256": str(write_env.get("envelope_sha256") or ""),
        "envelope_hash": str(sign_env.get("envelope_hash") or ""),
        "prev_hash": prev_hash,
        "disclosure_path": str(write_dis.get("disclosure_path") or ""),
    }


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_l4w_auditor_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "ESTER_L4W_PROFILE_DEFAULT",
        "ESTER_L4W_AUDIT_MAX_RECORDS",
        "ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE",
        "ESTER_L4W_AUDIT_REQUIRE_DISCLOSURE",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}

    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_L4W_PROFILE_DEFAULT"] = "HRO"
    os.environ["ESTER_L4W_AUDIT_MAX_RECORDS"] = "50"
    os.environ["ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE"] = "1"
    os.environ["ESTER_L4W_AUDIT_REQUIRE_DISCLOSURE"] = "0"

    try:
        if not bool(l4w_witness.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "l4w_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        if not bool(evidence_signing.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "evidence_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2

        agent_id = "agent_l4w_auditor_smoke"
        rec1 = _make_record(persist_dir, agent_id, "evt_smoke_1", "tools.l4w_auditor_verify_smoke", "first clear")
        rec2 = _make_record(persist_dir, agent_id, "evt_smoke_2", "tools.l4w_auditor_verify_smoke", "second clear")
        if not bool(rec1.get("ok")) or not bool(rec2.get("ok")):
            print(json.dumps({"ok": False, "error": "record_build_failed", "rec1": rec1, "rec2": rec2}, ensure_ascii=True, indent=2))
            return 2

        events_rows = [
            {
                "ts": int(rec1.get("ts") or 0),
                "type": "QUARANTINE_CLEAR",
                "agent_id": agent_id,
                "event_id": str(rec1.get("event_id") or ""),
                "severity": "HIGH",
                "reason_code": "TAMPER_SUSPECT",
                "step": "drift.quarantine.clear",
                "details": {
                    "evidence_sha256": str(rec1.get("evidence_sha256") or ""),
                    "l4w_envelope_hash": str(rec1.get("envelope_hash") or ""),
                    "quarantine_event_id": str(rec1.get("event_id") or ""),
                },
            },
            {
                "ts": int(rec2.get("ts") or 0),
                "type": "QUARANTINE_CLEAR",
                "agent_id": agent_id,
                "event_id": str(rec2.get("event_id") or ""),
                "severity": "HIGH",
                "reason_code": "TAMPER_SUSPECT",
                "step": "drift.quarantine.clear",
                "details": {
                    "evidence_sha256": str(rec2.get("evidence_sha256") or ""),
                    "l4w_envelope_hash": str(rec2.get("envelope_hash") or ""),
                    "quarantine_event_id": str(rec2.get("event_id") or ""),
                },
            },
        ]
        _append_jsonl((persist_dir / "capability_drift" / "quarantine_events.jsonl").resolve(), events_rows)

        state_payload = {
            agent_id: {
                "agent_id": agent_id,
                "active": False,
                "event_id": str(rec2.get("event_id") or ""),
                "cleared": {
                    "ts": int(rec2.get("ts") or 0),
                    "event_id": str(rec2.get("event_id") or ""),
                    "evidence_sha256": str(rec2.get("evidence_sha256") or ""),
                    "l4w_envelope_hash": str(rec2.get("envelope_hash") or ""),
                    "l4w_prev_hash": str(rec2.get("prev_hash") or ""),
                    "l4w_envelope_path": str(rec2.get("envelope_rel") or ""),
                    "l4w_envelope_sha256": str(rec2.get("envelope_sha256") or ""),
                },
            }
        }
        _write_json((persist_dir / "capability_drift" / "quarantine_state.json").resolve(), state_payload)

        journal_rows = [
            {
                "ts": int(rec1.get("ts") or 0),
                "step": "drift.quarantine.clear",
                "action_id": "drift.quarantine.clear",
                "agent_id": agent_id,
                "event_id": str(rec1.get("event_id") or ""),
                "metadata": {
                    "action_id": "drift.quarantine.clear",
                    "agent_id": agent_id,
                    "quarantine_event_id": str(rec1.get("event_id") or ""),
                    "evidence_sha256": str(rec1.get("evidence_sha256") or ""),
                    "l4w_envelope_hash": str(rec1.get("envelope_hash") or ""),
                },
            },
            {
                "ts": int(rec2.get("ts") or 0),
                "step": "drift.quarantine.clear",
                "action_id": "drift.quarantine.clear",
                "agent_id": agent_id,
                "event_id": str(rec2.get("event_id") or ""),
                "metadata": {
                    "action_id": "drift.quarantine.clear",
                    "agent_id": agent_id,
                    "quarantine_event_id": str(rec2.get("event_id") or ""),
                    "evidence_sha256": str(rec2.get("evidence_sha256") or ""),
                    "l4w_envelope_hash": str(rec2.get("envelope_hash") or ""),
                },
            },
        ]
        _append_jsonl((persist_dir / "volition" / "decisions.jsonl").resolve(), journal_rows)

        env = dict(os.environ)
        base_ok = _run_cli(agent_id, "BASE", persist_dir, env)
        hro_ok = _run_cli(agent_id, "HRO", persist_dir, env)
        full_ok = _run_cli(agent_id, "FULL", persist_dir, env)

        pass_base = int(base_ok.get("rc") or 0) == 0 and bool(base_ok.get("ok"))
        pass_hro = int(hro_ok.get("rc") or 0) == 0 and bool(hro_ok.get("ok"))
        pass_full = int(full_ok.get("rc") or 0) == 0 and bool(full_ok.get("ok"))

        envelope_path = Path(str(rec2.get("envelope_path") or "")).resolve()
        envelope_backup = envelope_path.read_bytes()
        tampered_envelope = bytearray(envelope_backup)
        if tampered_envelope:
            tampered_envelope[-1] = 65 if tampered_envelope[-1] != 65 else 66
            envelope_path.write_bytes(bytes(tampered_envelope))

        env_base_fail = _run_cli(agent_id, "BASE", persist_dir, env)
        env_hro_fail = _run_cli(agent_id, "HRO", persist_dir, env)
        env_full_fail = _run_cli(agent_id, "FULL", persist_dir, env)
        envelope_path.write_bytes(envelope_backup)

        env_fail_codes = _error_codes(env_base_fail) + _error_codes(env_hro_fail) + _error_codes(env_full_fail)
        env_fail_ok = (
            int(env_base_fail.get("rc") or 0) == 2
            and int(env_hro_fail.get("rc") or 0) == 2
            and int(env_full_fail.get("rc") or 0) == 2
            and any(code in {"L4W_HASH_MISMATCH", "L4W_SIG_INVALID"} for code in env_fail_codes)
        )

        evidence_path = Path(str(rec2.get("evidence_path") or "")).resolve()
        evidence_backup = evidence_path.read_text(encoding="utf-8")
        evidence_obj = json.loads(evidence_backup)
        evidence_obj["summary"] = str(evidence_obj.get("summary") or "") + " tampered"
        evidence_path.write_text(json.dumps(evidence_obj, ensure_ascii=True, indent=2), encoding="utf-8")

        ev_base_fail = _run_cli(agent_id, "BASE", persist_dir, env)
        ev_hro_fail = _run_cli(agent_id, "HRO", persist_dir, env)
        ev_full_fail = _run_cli(agent_id, "FULL", persist_dir, env)
        evidence_path.write_text(evidence_backup, encoding="utf-8")

        ev_base_codes = _error_codes(ev_base_fail)
        ev_hro_codes = _error_codes(ev_hro_fail)
        ev_full_codes = _error_codes(ev_full_fail)
        ev_fail_ok = (
            int(ev_base_fail.get("rc") or 0) == 2
            and int(ev_hro_fail.get("rc") or 0) == 2
            and int(ev_full_fail.get("rc") or 0) == 2
            and ("EVIDENCE_HASH_MISMATCH" in ev_base_codes)
            and ("EVIDENCE_HASH_MISMATCH" in ev_hro_codes)
            and ("EVIDENCE_HASH_MISMATCH" in ev_full_codes)
            and any(code in {"EVIDENCE_SIG_INVALID", "EVIDENCE_PAYLOAD_HASH_MISMATCH"} for code in ev_hro_codes)
            and any(code in {"EVIDENCE_SIG_INVALID", "EVIDENCE_PAYLOAD_HASH_MISMATCH"} for code in ev_full_codes)
        )

        ok = bool(pass_base and pass_hro and pass_full and env_fail_ok and ev_fail_ok)
        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "persist_dir": str(persist_dir),
            "agent_id": agent_id,
            "base_ok": base_ok,
            "hro_ok": hro_ok,
            "full_ok": full_ok,
            "tamper_envelope": {
                "base": env_base_fail,
                "hro": env_hro_fail,
                "full": env_full_fail,
            },
            "tamper_evidence": {
                "base": ev_base_fail,
                "hro": ev_hro_fail,
                "full": ev_full_fail,
            },
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
