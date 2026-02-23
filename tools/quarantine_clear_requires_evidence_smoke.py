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
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_factory
from modules.runtime import capability_drift, drift_quarantine, evidence_signing, l4w_witness
from modules.thinking import action_registry


def _read_json(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _write_evidence_packet(persist_dir: Path, agent_id: str, event_id: str) -> Dict[str, str]:
    evidence_root = (persist_dir / "capability_drift" / "evidence").resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    file_name = f"{agent_id}_{event_id}_{ts}.json"
    evidence_path = (evidence_root / file_name).resolve()
    packet = {
        "schema": "ester.evidence.v1",
        "created_ts": ts,
        "reviewer": "tools.quarantine_clear_requires_evidence_smoke",
        "agent_id": str(agent_id or ""),
        "quarantine_event_id": str(event_id or ""),
        "decision": "CLEAR_QUARANTINE",
        "summary": "validated tamper and rollback path",
        "findings": {"tamper_detected": True, "restore_ready": True},
        "artifacts": [],
    }
    sign_rep = evidence_signing.sign_packet(dict(packet))
    signed_packet = dict(sign_rep.get("packet") or packet)
    evidence_path.write_text(json.dumps(signed_packet, ensure_ascii=True, indent=2), encoding="utf-8")
    sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    return {"path": file_name, "sha256": sha256, "full_path": str(evidence_path)}


def _write_l4w_envelope(agent_id: str, event_id: str, evidence: Dict[str, str]) -> Dict[str, str]:
    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    built = l4w_witness.build_envelope_for_clear(
        agent_id,
        event_id,
        reviewer="tools.quarantine_clear_requires_evidence_smoke",
        summary="validated tamper and rollback path",
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
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_quarantine_clear_requires_evidence_smoke_")).resolve()
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
    os.environ["ESTER_DRIFT_TTL_SEC"] = "1"
    os.environ["ESTER_QUARANTINE_TTL_SEC"] = "1"
    os.environ["ESTER_QUARANTINE_FAIL_MAX"] = "3"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_quarantine_clear_requires_evidence_smoke",
                "goal": "clear requires evidence smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.quarantine_clear_requires_evidence_smoke",
                "budgets": {"max_actions": 6, "max_work_ms": 3000, "window": 60, "est_work_ms": 250},
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

        spec = _read_json(spec_path)
        tampered_allow = drift_quarantine.normalize_allowlist(list(spec.get("allowed_actions") or []) + ["llm.remote.call"])
        spec["allowed_actions"] = tampered_allow
        spec["allowed_actions_hash"] = capability_drift.allowlist_hash(tampered_allow)
        _write_json(spec_path, spec)

        q_set = drift_quarantine.ensure_quarantine_for_agent(agent_id, source="evidence_smoke")
        event_id = str(q_set.get("event_id") or "")

        clear_missing = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "missing evidence should fail",
                "by": "tools.quarantine_clear_requires_evidence_smoke",
                "chain_id": "chain_quarantine_clear_requires_evidence_missing",
            },
        )
        state_after_missing = drift_quarantine.is_quarantined(agent_id)

        evidence = _write_evidence_packet(persist_dir, agent_id, event_id)
        clear_bad_hash = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "bad evidence hash should fail",
                "by": "tools.quarantine_clear_requires_evidence_smoke",
                "chain_id": "chain_quarantine_clear_requires_evidence_bad_hash",
                "evidence": {"path": str(evidence.get("path") or ""), "sha256": "0" * 64},
            },
        )
        state_after_bad_hash = drift_quarantine.is_quarantined(agent_id)

        clear_ok = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": event_id,
                "reason": "evidence approved",
                "by": "tools.quarantine_clear_requires_evidence_smoke",
                "chain_id": "chain_quarantine_clear_requires_evidence_ok",
                "evidence": {"path": str(evidence.get("path") or ""), "sha256": str(evidence.get("sha256") or "")},
                "evidence_note": "smoke evidence packet",
                "l4w": _write_l4w_envelope(agent_id, event_id, evidence),
            },
        )
        state_after_ok = drift_quarantine.is_quarantined(agent_id)
        spec_path.write_bytes(original_spec_bytes)

        enqueue_after = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "after evidence clear",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "evidence_clear_after",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "ok2.txt", "content": "ok"}}],
                },
            },
        )

        events_path = (persist_dir / "capability_drift" / "quarantine_events.jsonl").resolve()
        events = _read_jsonl(events_path)
        clear_events = [
            row
            for row in events
            if str(row.get("type") or "") == "QUARANTINE_CLEAR"
            and str(row.get("agent_id") or "") == agent_id
            and str(row.get("event_id") or "") == event_id
        ]
        clear_event = dict(clear_events[-1] if clear_events else {})
        clear_details = dict(clear_event.get("details") or {})

        volition_path = (persist_dir / "volition" / "decisions.jsonl").resolve()
        volition_rows = _read_jsonl(volition_path)
        volition_clear = {}
        for row in reversed(volition_rows):
            if str(row.get("action_id") or row.get("action_kind") or "") != "drift.quarantine.clear":
                continue
            md = dict(row.get("metadata") or {})
            if str(md.get("agent_id") or "") != agent_id:
                continue
            if str(md.get("evidence_hash") or "") == str(evidence.get("sha256") or ""):
                volition_clear = row
                break

        ok = (
            bool(baseline.get("ok"))
            and bool(q_set.get("ok"))
            and bool(q_set.get("active"))
            and (not bool(clear_missing.get("ok")))
            and str(clear_missing.get("error_code") or "") == "EVIDENCE_REQUIRED"
            and bool(state_after_missing.get("active"))
            and (not bool(clear_bad_hash.get("ok")))
            and str(clear_bad_hash.get("error_code") or "") in {"EVIDENCE_HASH_MISMATCH", "EVIDENCE_INVALID"}
            and bool(state_after_bad_hash.get("active"))
            and bool(clear_ok.get("ok"))
            and bool(clear_ok.get("cleared"))
            and str(clear_ok.get("evidence_sha256") or "") == str(evidence.get("sha256") or "")
            and (not bool(state_after_ok.get("active")))
            and bool(enqueue_after.get("ok"))
            and bool(clear_event)
            and str(clear_details.get("evidence_sha256") or "") == str(evidence.get("sha256") or "")
            and str(clear_details.get("evidence_path") or "") == str(evidence.get("path") or "")
            and bool(volition_clear)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "baseline": baseline,
            "q_set": q_set,
            "evidence": evidence,
            "clear_missing": clear_missing,
            "state_after_missing": state_after_missing,
            "clear_bad_hash": clear_bad_hash,
            "state_after_bad_hash": state_after_bad_hash,
            "clear_ok": clear_ok,
            "state_after_ok": state_after_ok,
            "enqueue_after": enqueue_after,
            "events_path": str(events_path),
            "clear_event": clear_event,
            "volition_path": str(volition_path),
            "volition_clear": volition_clear,
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
