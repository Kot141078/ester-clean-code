# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory
from modules.runtime import drift_quarantine, evidence_signing, l4w_witness
from modules.thinking import action_registry


def _write_packet(persist_dir: Path, name: str, packet: Dict[str, Any]) -> Dict[str, str]:
    evidence_root = (persist_dir / "capability_drift" / "evidence").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    p = (evidence_root / name).resolve()
    p.write_text(json.dumps(packet, ensure_ascii=True, indent=2), encoding="utf-8")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"path": str(name), "sha256": str(sha), "full_path": str(p)}


def _base_packet(agent_id: str, event_id: str, reviewer: str, summary: str) -> Dict[str, Any]:
    return {
        "schema": "ester.evidence.v1",
        "created_ts": int(time.time()),
        "reviewer": str(reviewer or ""),
        "agent_id": str(agent_id or ""),
        "quarantine_event_id": str(event_id or ""),
        "decision": "CLEAR_QUARANTINE",
        "summary": str(summary or "")[:200],
        "findings": {"smoke": True},
        "artifacts": [],
    }


def _sign_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    rep = evidence_signing.sign_packet(dict(packet))
    if bool(rep.get("ok")) and isinstance(rep.get("packet"), dict):
        return dict(rep.get("packet") or {})
    return dict(packet)


def _write_l4w_envelope(agent_id: str, event_id: str, evidence: Dict[str, str], summary: str) -> Dict[str, str]:
    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    built = l4w_witness.build_envelope_for_clear(
        agent_id,
        event_id,
        reviewer="tools.evidence_signature_smoke",
        summary=str(summary or ""),
        notes=None,
        evidence_path=str(evidence.get("path") or ""),
        evidence_sha256=str(evidence.get("sha256") or ""),
        evidence_schema="ester.evidence.v1",
        evidence_sig_ok=True,
        evidence_payload_hash="",
        prev_hash=prev_hash,
        on_time=True,
        late=False,
    )
    signed = l4w_witness.sign_envelope(dict(built.get("envelope") or {}))
    written = l4w_witness.write_envelope(agent_id, dict(signed.get("envelope") or {}))
    return {
        "envelope_path": str(written.get("envelope_rel_path") or ""),
        "envelope_sha256": str(written.get("envelope_sha256") or ""),
    }


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_evidence_signature_smoke_")).resolve()
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
        "ESTER_DRIFT_TTL_SEC",
        "ESTER_QUARANTINE_TTL_SEC",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_EVIDENCE_SIG_REQUIRED"] = "1"
    os.environ["ESTER_DRIFT_TTL_SEC"] = "1"
    os.environ["ESTER_QUARANTINE_TTL_SEC"] = "1"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_evidence_signature_smoke",
                "goal": "evidence signature smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.evidence_signature_smoke",
                "budgets": {"max_actions": 4, "max_work_ms": 2000, "window": 60, "est_work_ms": 200},
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2
        agent_id = str(create.get("agent_id") or "")

        q_set = drift_quarantine.set_manual_quarantine(
            agent_id,
            reason_code="EVIDENCE_SIGNATURE_SMOKE",
            severity="HIGH",
            kind="evidence_signature_smoke",
            source="tools.evidence_signature_smoke",
        )
        event_id = str(q_set.get("event_id") or "")

        unsigned_packet = _base_packet(agent_id, event_id, "tools.evidence_signature_smoke", "unsigned should fail")
        unsigned_evidence = _write_packet(persist_dir, "unsigned.json", unsigned_packet)
        clear_unsigned = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "unsigned",
                "by": "tools.evidence_signature_smoke",
                "chain_id": "chain_evidence_sig_unsigned",
                "evidence": {"path": unsigned_evidence["path"], "sha256": unsigned_evidence["sha256"]},
            },
        )

        invalid_packet = _sign_packet(_base_packet(agent_id, event_id, "tools.evidence_signature_smoke", "invalid sig"))
        sig = dict(invalid_packet.get("sig") or {})
        sig_b64 = str(sig.get("sig_b64") or "")
        if sig_b64:
            sig["sig_b64"] = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
            invalid_packet["sig"] = sig
        invalid_evidence = _write_packet(persist_dir, "invalid.json", invalid_packet)
        clear_invalid = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "invalid",
                "by": "tools.evidence_signature_smoke",
                "chain_id": "chain_evidence_sig_invalid",
                "evidence": {"path": invalid_evidence["path"], "sha256": invalid_evidence["sha256"]},
            },
        )

        valid_packet = _sign_packet(_base_packet(agent_id, event_id, "tools.evidence_signature_smoke", "valid sig"))
        valid_evidence = _write_packet(persist_dir, "valid.json", valid_packet)
        valid_l4w = _write_l4w_envelope(agent_id, event_id, valid_evidence, "valid sig")
        clear_valid = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "valid",
                "by": "tools.evidence_signature_smoke",
                "chain_id": "chain_evidence_sig_valid",
                "evidence": {"path": valid_evidence["path"], "sha256": valid_evidence["sha256"]},
                "l4w": {"envelope_path": valid_l4w["envelope_path"], "envelope_sha256": valid_l4w["envelope_sha256"]},
            },
        )

        q_after = drift_quarantine.is_quarantined(agent_id)

        ok = (
            bool(create.get("ok"))
            and bool(q_set.get("ok"))
            and bool(q_set.get("active"))
            and (not bool(clear_unsigned.get("ok")))
            and str(clear_unsigned.get("error_code") or "") == "EVIDENCE_SIG_REQUIRED"
            and (not bool(clear_invalid.get("ok")))
            and str(clear_invalid.get("error_code") or "") in {"EVIDENCE_SIG_INVALID", "EVIDENCE_PAYLOAD_HASH_MISMATCH"}
            and bool(clear_valid.get("ok"))
            and bool(clear_valid.get("cleared"))
            and bool(clear_valid.get("evidence_sig_ok"))
            and (not bool(q_after.get("active")))
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "q_set": q_set,
            "unsigned_evidence": unsigned_evidence,
            "clear_unsigned": clear_unsigned,
            "invalid_evidence": invalid_evidence,
            "clear_invalid": clear_invalid,
            "valid_evidence": valid_evidence,
            "clear_valid": clear_valid,
            "q_after": q_after,
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
