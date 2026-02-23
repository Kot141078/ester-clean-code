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
        "findings": {"smoke": True, "expired": True},
        "artifacts": [],
    }
    sign_rep = evidence_signing.sign_packet(dict(packet))
    signed_packet = dict(sign_rep.get("packet") or packet)
    evidence_path.write_text(json.dumps(signed_packet, ensure_ascii=True, indent=2), encoding="utf-8")
    sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    return {"path": file_name, "sha256": sha256}


def _write_l4w_envelope(agent_id: str, event_id: str, evidence: Dict[str, str], reviewer: str, summary: str) -> Dict[str, str]:
    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    built = l4w_witness.build_envelope_for_clear(
        agent_id,
        event_id,
        reviewer=reviewer,
        summary=summary,
        notes=None,
        evidence_path=str(evidence.get("path") or ""),
        evidence_sha256=str(evidence.get("sha256") or ""),
        evidence_schema="ester.evidence.v1",
        evidence_sig_ok=True,
        evidence_payload_hash="",
        prev_hash=prev_hash,
        on_time=False,
        late=True,
    )
    signed = l4w_witness.sign_envelope(dict(built.get("envelope") or {}))
    written = l4w_witness.write_envelope(agent_id, dict(signed.get("envelope") or {}))
    return {
        "envelope_path": str(written.get("envelope_rel_path") or ""),
        "envelope_sha256": str(written.get("envelope_sha256") or ""),
    }


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_quarantine_challenge_window_smoke_")).resolve()
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
        "ESTER_QUARANTINE_CHALLENGE_SEC",
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
    os.environ["ESTER_QUARANTINE_CHALLENGE_SEC"] = "2"

    try:
        create = agent_factory.create_agent(
            {
                "name": "agent_quarantine_challenge_window_smoke",
                "goal": "challenge window smoke",
                "template_id": "builder.v1",
                "capabilities": ["cap.fs.sandbox.write"],
                "owner": "tools.quarantine_challenge_window_smoke",
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
        tampered_allow = drift_quarantine.normalize_allowlist(
            list(spec.get("allowed_actions") or []) + ["llm.remote.call"]
        )
        spec["allowed_actions"] = tampered_allow
        spec["allowed_actions_hash"] = capability_drift.allowlist_hash(tampered_allow)
        _write_json(spec_path, spec)

        q_set = drift_quarantine.ensure_quarantine_for_agent(agent_id, source="challenge_smoke")
        enqueue_block = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "challenge_window_block",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "challenge_window_block",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "ok.txt", "content": "ok"}}],
                },
            },
        )

        # Runtime clamps challenge_sec to >=60; force an elapsed deadline in fixture state
        # to keep smoke fast while preserving production clamp semantics.
        state_path = (persist_dir / "capability_drift" / "quarantine_state.json").resolve()
        forced_deadline_ts = int(time.time()) - 1
        state_before = _read_json(state_path)
        state_row_before = dict(state_before.get(agent_id) or {})
        if state_row_before:
            state_row_before["challenge_deadline_ts"] = int(forced_deadline_ts)
            state_row_before["expired"] = False
            state_row_before["expired_ts"] = 0
            state_row_before["expired_event_id"] = ""
            state_before[agent_id] = state_row_before
            _write_json(state_path, state_before)

        time.sleep(3.2)

        q_after = drift_quarantine.ensure_quarantine_for_agent(agent_id, source="challenge_smoke_after")
        status = drift_quarantine.build_drift_quarantine_status()

        state = _read_json(state_path)
        state_row = dict(state.get(agent_id) or {})
        events_path = (persist_dir / "capability_drift" / "quarantine_events.jsonl").resolve()
        events = _read_jsonl(events_path)
        event_types = [str(row.get("type") or "") for row in events]

        clear_evidence = _write_evidence_packet(
            persist_dir,
            agent_id,
            str(q_set.get("event_id") or ""),
            "tools.quarantine_challenge_window_smoke",
            "late manual review",
        )
        clear_rep = action_registry.invoke_guarded(
            "drift.quarantine.clear",
            {
                "agent_id": agent_id,
                "event_id": str(q_set.get("event_id") or ""),
                "reason": "late manual review",
                "by": "tools.quarantine_challenge_window_smoke",
                "chain_id": "chain_quarantine_challenge_window_smoke_clear",
                "evidence": dict(clear_evidence),
                "evidence_note": "smoke late clear",
                "l4w": _write_l4w_envelope(
                    agent_id,
                    str(q_set.get("event_id") or ""),
                    clear_evidence,
                    "tools.quarantine_challenge_window_smoke",
                    "late manual review",
                ),
            },
        )
        spec_path.write_bytes(original_spec_bytes)

        enqueue_after = action_registry.invoke(
            "agent.queue.enqueue",
            {
                "agent_id": agent_id,
                "actor": "ester:smoke",
                "reason": "challenge_window_after_clear",
                "challenge_sec": 0,
                "plan": {
                    "schema": "ester.plan.v1",
                    "plan_id": "challenge_window_after_clear",
                    "steps": [{"action": "files.sandbox_write", "args": {"relpath": "ok2.txt", "content": "ok"}}],
                },
            },
        )

        ok = (
            bool(baseline.get("ok"))
            and bool(q_set.get("ok"))
            and bool(q_set.get("active"))
            and int(q_set.get("challenge_deadline_ts") or 0) > int(q_set.get("challenge_open_ts") or 0)
            and (not bool(enqueue_block.get("ok")))
            and str(enqueue_block.get("error_code") or "") == "DRIFT_QUARANTINED"
            and bool(q_after.get("active"))
            and bool(q_after.get("expired"))
            and int(q_after.get("overdue_sec") or 0) >= 1
            and bool(state_row.get("expired"))
            and ("QUARANTINE_EXPIRED" in event_types)
            and bool(clear_rep.get("ok"))
            and bool(clear_rep.get("cleared"))
            and bool(clear_rep.get("late"))
            and (not bool(clear_rep.get("on_time")))
            and str(clear_rep.get("evidence_sha256") or "") == str(clear_evidence.get("sha256") or "")
            and bool(enqueue_after.get("ok"))
            and bool(status.get("summary"))
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "baseline": baseline,
            "q_set": q_set,
            "enqueue_block": enqueue_block,
            "q_after": q_after,
            "forced_deadline_ts": int(forced_deadline_ts),
            "state_row": state_row,
            "status": status,
            "clear_evidence": clear_evidence,
            "clear_rep": clear_rep,
            "enqueue_after": enqueue_after,
            "events_path": str(events_path),
            "event_types": event_types,
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
