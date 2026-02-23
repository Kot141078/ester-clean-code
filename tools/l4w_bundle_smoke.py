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


def _run_json(args: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    proc = subprocess.run(args, capture_output=True, text=True, env=env)
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
    signed_packet = dict(signed.get("packet") or {})
    _write_json(evidence_path, signed_packet)
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()

    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "") if bool(head.get("has_head")) else ""
    built = l4w_witness.build_envelope_for_clear(
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
    if not bool(built.get("ok")):
        return {"ok": False, "stage": "build_envelope", "details": built}
    signed_env = l4w_witness.sign_envelope(dict(built.get("envelope") or {}))
    if not bool(signed_env.get("ok")):
        return {"ok": False, "stage": "sign_envelope", "details": signed_env}
    write_env = l4w_witness.write_envelope(agent_id, dict(signed_env.get("envelope") or {}))
    if not bool(write_env.get("ok")):
        return {"ok": False, "stage": "write_envelope", "details": write_env}
    append = l4w_witness.append_chain_record(
        agent_id,
        quarantine_event_id=event_id,
        envelope_id=str((dict(signed_env.get("envelope") or {})).get("envelope_id") or ""),
        envelope_hash=str(signed_env.get("envelope_hash") or ""),
        prev_hash=prev_hash,
        envelope_path=str(write_env.get("envelope_rel_path") or ""),
        envelope_sha256=str(write_env.get("envelope_sha256") or ""),
        ts=int((dict(signed_env.get("envelope") or {})).get("ts") or ts),
    )
    if not bool(append.get("ok")):
        return {"ok": False, "stage": "append_chain", "details": append}
    disclosure = l4w_witness.build_disclosure(
        str(signed_env.get("envelope_hash") or ""),
        list((dict(built.get("disclosure_template") or {})).get("reveals") or []),
        sign=True,
    )
    write_dis = l4w_witness.write_disclosure(disclosure)
    if not bool(write_dis.get("ok")):
        return {"ok": False, "stage": "write_disclosure", "details": write_dis}
    return {
        "ok": True,
        "ts": int((dict(signed_env.get("envelope") or {})).get("ts") or ts),
        "event_id": event_id,
        "evidence_rel": evidence_rel,
        "evidence_path": str(evidence_path),
        "evidence_sha256": evidence_sha,
        "envelope_rel": str(write_env.get("envelope_rel_path") or ""),
        "envelope_path": str(write_env.get("envelope_path") or ""),
        "envelope_sha256": str(write_env.get("envelope_sha256") or ""),
        "envelope_hash": str(signed_env.get("envelope_hash") or ""),
        "prev_hash": prev_hash,
    }


def _export_bundle(env: Dict[str, str], *, agent_id: str, out_dir: Path, profile: str, include_evidence: bool = False, include_disclosures: bool = False, include_cross_refs: bool = False, zip_mode: bool = False) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str((ROOT / "tools" / "export_audit_bundle.py").resolve()),
        "--agent-id",
        agent_id,
        "--out",
        str(out_dir),
        "--profile",
        profile,
        "--json",
    ]
    if include_evidence:
        cmd.append("--include-evidence-files")
    if include_disclosures:
        cmd.append("--include-disclosures")
    if include_cross_refs:
        cmd.append("--include-cross-refs")
    if zip_mode:
        cmd.append("--zip")
    return _run_json(cmd, env)


def _verify_bundle(env: Dict[str, str], *, bundle: Path, profile: str) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str((ROOT / "tools" / "auditor_verify_bundle.py").resolve()),
        "--bundle",
        str(bundle),
        "--profile",
        profile,
        "--json",
    ]
    return _run_json(cmd, env)


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_l4w_bundle_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    out_root = (tmp_root / "out").resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "ESTER_L4W_PROFILE_DEFAULT",
        "ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE",
        "ESTER_L4W_AUDIT_REQUIRE_DISCLOSURE",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_L4W_PROFILE_DEFAULT"] = "HRO"
    os.environ["ESTER_L4W_AUDIT_REQUIRE_EVIDENCE_FILE"] = "1"
    os.environ["ESTER_L4W_AUDIT_REQUIRE_DISCLOSURE"] = "0"

    try:
        if not bool(l4w_witness.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "l4w_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        if not bool(evidence_signing.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "evidence_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2

        agent_id = "agent_l4w_bundle_smoke"
        rec1 = _make_record(persist_dir, agent_id, "evt_bundle_1", "tools.l4w_bundle_smoke", "first")
        rec2 = _make_record(persist_dir, agent_id, "evt_bundle_2", "tools.l4w_bundle_smoke", "second")
        if not bool(rec1.get("ok")) or not bool(rec2.get("ok")):
            print(json.dumps({"ok": False, "error": "record_build_failed", "rec1": rec1, "rec2": rec2}, ensure_ascii=True, indent=2))
            return 2

        _append_jsonl(
            (persist_dir / "capability_drift" / "quarantine_events.jsonl").resolve(),
            [
                {
                    "ts": int(rec1.get("ts") or 0),
                    "type": "QUARANTINE_CLEAR",
                    "agent_id": agent_id,
                    "event_id": str(rec1.get("event_id") or ""),
                    "details": {
                        "l4w_envelope_hash": str(rec1.get("envelope_hash") or ""),
                        "evidence_sha256": str(rec1.get("evidence_sha256") or ""),
                    },
                },
                {
                    "ts": int(rec2.get("ts") or 0),
                    "type": "QUARANTINE_CLEAR",
                    "agent_id": agent_id,
                    "event_id": str(rec2.get("event_id") or ""),
                    "details": {
                        "l4w_envelope_hash": str(rec2.get("envelope_hash") or ""),
                        "evidence_sha256": str(rec2.get("evidence_sha256") or ""),
                    },
                },
            ],
        )
        _append_jsonl(
            (persist_dir / "volition" / "decisions.jsonl").resolve(),
            [
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
            ],
        )

        env = dict(os.environ)

        base_dir = (out_root / "bundle_base").resolve()
        exp_base = _export_bundle(env, agent_id=agent_id, out_dir=base_dir, profile="BASE")
        ver_base_dir = _verify_bundle(env, bundle=base_dir, profile="BASE")

        base_zip_dir = (out_root / "bundle_base_zip").resolve()
        exp_zip = _export_bundle(env, agent_id=agent_id, out_dir=base_zip_dir, profile="BASE", zip_mode=True)
        zip_path = Path(str(exp_zip.get("bundle_zip") or "")).resolve()
        ver_base_zip = _verify_bundle(env, bundle=zip_path, profile="BASE")

        tamper_env_path = Path(str(rec2.get("envelope_rel") or ""))
        target_env = (base_dir / "l4w" / "envelopes" / tamper_env_path).resolve()
        tampered = _read_json(target_env) if target_env.exists() else {}
        if tampered:
            claim = dict(tampered.get("claim") or {})
            claim["decision"] = "CLEAR_QUARANTINE_TAMPERED"
            tampered["claim"] = claim
            _write_json(target_env, tampered)
        ver_tampered = _verify_bundle(env, bundle=base_dir, profile="BASE")

        hro_with_ev_dir = (out_root / "bundle_hro_with_ev").resolve()
        exp_hro_with_ev = _export_bundle(
            env,
            agent_id=agent_id,
            out_dir=hro_with_ev_dir,
            profile="HRO",
            include_evidence=True,
            include_disclosures=True,
        )
        ver_hro_with_ev = _verify_bundle(env, bundle=hro_with_ev_dir, profile="HRO")

        hro_no_ev_dir = (out_root / "bundle_hro_no_ev").resolve()
        exp_hro_no_ev = _export_bundle(
            env,
            agent_id=agent_id,
            out_dir=hro_no_ev_dir,
            profile="HRO",
            include_disclosures=True,
        )
        ver_hro_no_ev = _verify_bundle(env, bundle=hro_no_ev_dir, profile="HRO")

        full_with_refs_dir = (out_root / "bundle_full_with_refs").resolve()
        exp_full_with_refs = _export_bundle(
            env,
            agent_id=agent_id,
            out_dir=full_with_refs_dir,
            profile="FULL",
            include_evidence=True,
            include_disclosures=True,
            include_cross_refs=True,
        )
        ver_full_with_refs = _verify_bundle(env, bundle=full_with_refs_dir, profile="FULL")

        full_no_refs_dir = (out_root / "bundle_full_no_refs").resolve()
        exp_full_no_refs = _export_bundle(
            env,
            agent_id=agent_id,
            out_dir=full_no_refs_dir,
            profile="FULL",
            include_evidence=True,
            include_disclosures=True,
        )
        ver_full_no_refs = _verify_bundle(env, bundle=full_no_refs_dir, profile="FULL")

        tamper_codes = _error_codes(ver_tampered)
        hro_no_ev_codes = _error_codes(ver_hro_no_ev)
        full_no_refs_codes = _error_codes(ver_full_no_refs)

        ok = (
            bool(exp_base.get("ok"))
            and int(ver_base_dir.get("rc") or 0) == 0
            and bool(exp_zip.get("ok"))
            and zip_path.exists()
            and int(ver_base_zip.get("rc") or 0) == 0
            and int(ver_tampered.get("rc") or 0) == 2
            and any(code in {"L4W_HASH_MISMATCH", "L4W_SIG_INVALID"} for code in tamper_codes)
            and bool(exp_hro_with_ev.get("ok"))
            and int(ver_hro_with_ev.get("rc") or 0) == 0
            and bool(exp_hro_no_ev.get("ok"))
            and int(ver_hro_no_ev.get("rc") or 0) == 2
            and ("EVIDENCE_FILES_MISSING_FOR_HRO" in hro_no_ev_codes)
            and bool(exp_full_with_refs.get("ok"))
            and int(ver_full_with_refs.get("rc") or 0) == 0
            and bool(exp_full_no_refs.get("ok"))
            and int(ver_full_no_refs.get("rc") or 0) == 2
            and ("FULL_REFS_MISSING" in full_no_refs_codes)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "base": {"export": exp_base, "verify_dir": ver_base_dir, "verify_zip": ver_base_zip, "export_zip": exp_zip},
            "tampered_base": ver_tampered,
            "hro": {"with_evidence": ver_hro_with_ev, "no_evidence": ver_hro_no_ev, "export_with": exp_hro_with_ev, "export_without": exp_hro_no_ev},
            "full": {"with_refs": ver_full_with_refs, "without_refs": ver_full_no_refs, "export_with": exp_full_with_refs, "export_without": exp_full_no_refs},
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


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
