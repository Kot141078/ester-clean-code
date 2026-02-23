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
from tools.build_integrity_manifest import DEFAULT_RELPATHS, build_manifest


def _read_json(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    return {}


def _write_signed_evidence(persist_dir: Path, packet: Dict[str, Any], name: str) -> Dict[str, str]:
    evidence_root = (persist_dir / "capability_drift" / "evidence").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    signed = evidence_signing.sign_packet(dict(packet))
    signed_packet = dict(signed.get("packet") or packet)
    p = (evidence_root / name).resolve()
    p.write_text(json.dumps(signed_packet, ensure_ascii=True, indent=2), encoding="utf-8")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"path": str(name), "sha256": str(sha), "full_path": str(p)}


def _write_l4w_envelope(agent_id: str, event_id: str, evidence: Dict[str, str]) -> Dict[str, str]:
    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    built = l4w_witness.build_envelope_for_clear(
        agent_id,
        event_id,
        reviewer="tools.spec_guard_smoke",
        summary="spec restored, tamper cleared",
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
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_spec_guard_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    manifest_path = (tmp_root / "manifest" / "template_capability_SHA256SUMS.json").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    build_rep = build_manifest(root=ROOT, out_path=manifest_path, relpaths=list(DEFAULT_RELPATHS))

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_VOLITION_ALLOWED_HOURS",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
        "ESTER_INTEGRITY_MANIFEST_PATH",
        "ESTER_INTEGRITY_TTL_SEC",
        "ESTER_EVIDENCE_SIG_REQUIRED",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_INTEGRITY_MANIFEST_PATH"] = str(manifest_path)
    os.environ["ESTER_INTEGRITY_TTL_SEC"] = "1"
    os.environ["ESTER_EVIDENCE_SIG_REQUIRED"] = "1"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_spec_guard_smoke",
                "goal": "spec guard smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.spec_guard_smoke",
                "budgets": {"max_actions": 4, "max_work_ms": 2000, "window": 60, "est_work_ms": 200},
                "oracle_policy": {"allow_remote": False},
            }
        )
        if not bool(create.get("ok")):
            print(json.dumps({"ok": False, "error": "create_failed", "create": create}, ensure_ascii=True, indent=2))
            return 2
        agent_id = str(create.get("agent_id") or "")
        spec_path = Path(str(create.get("spec_path") or "")).resolve()
        original_bytes = spec_path.read_bytes()

        guard_path = (persist_dir / "integrity" / "spec_guard.json").resolve()
        guard_before = _read_json(guard_path)
        guard_entry_before = dict((dict(guard_before.get("agents") or {})).get(agent_id) or {})

        spec = _read_json(spec_path)
        spec["tamper_marker"] = "spec_guard_smoke"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        enqueue_tamper = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "spec_tamper",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "spec_guard_tamper",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "bad.txt", "content": "bad"}}],
                },
            },
        )

        q_after_tamper = drift_quarantine.is_quarantined(agent_id)
        event_id = str((dict(enqueue_tamper.get("quarantine") or {})).get("event_id") or q_after_tamper.get("event_id") or "")

        spec_path.write_bytes(original_bytes)

        packet = {
            "schema": "ester.evidence.v1",
            "created_ts": int(time.time()),
            "reviewer": "tools.spec_guard_smoke",
            "agent_id": agent_id,
            "quarantine_event_id": event_id,
            "decision": "CLEAR_QUARANTINE",
            "summary": "spec restored, tamper cleared",
            "findings": {"tamper": True, "restored": True},
            "artifacts": [],
        }
        clear_evidence = _write_signed_evidence(persist_dir, packet, "spec_guard_clear.json")
        clear_rep = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "spec restored",
                "by": "tools.spec_guard_smoke",
                "chain_id": "chain_spec_guard_clear",
                "evidence": {"path": clear_evidence["path"], "sha256": clear_evidence["sha256"]},
                "evidence_note": "spec restored in smoke",
                "l4w": _write_l4w_envelope(agent_id, event_id, clear_evidence),
            },
        )

        enqueue_after = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "spec_restored",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "spec_guard_restored",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "ok.txt", "content": "ok"}}],
                },
            },
        )
        q_after_clear = drift_quarantine.is_quarantined(agent_id)
        guard_after = _read_json(guard_path)

        ok = (
            bool(build_rep.get("ok"))
            and bool(create.get("ok"))
            and bool(guard_entry_before)
            and (not bool(enqueue_tamper.get("ok")))
            and str(enqueue_tamper.get("error_code") or "") == "SPEC_TAMPER_NO_JOURNAL"
            and bool(q_after_tamper.get("active"))
            and bool(event_id)
            and bool(clear_rep.get("ok"))
            and bool(clear_rep.get("evidence_sig_ok"))
            and (not bool(q_after_clear.get("active")))
            and bool(enqueue_after.get("ok"))
            and bool(guard_after.get("agents"))
        )

        out: Dict[str, Any] = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "manifest_path": str(manifest_path),
            "build_manifest": build_rep,
            "agent_id": agent_id,
            "guard_path": str(guard_path),
            "guard_before": guard_before,
            "enqueue_tamper": enqueue_tamper,
            "q_after_tamper": q_after_tamper,
            "event_id": event_id,
            "clear_evidence": clear_evidence,
            "clear_rep": clear_rep,
            "q_after_clear": q_after_clear,
            "enqueue_after": enqueue_after,
            "guard_after": guard_after,
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
