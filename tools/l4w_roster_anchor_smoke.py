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

from modules.runtime import bundle_signing, evidence_signing, l4w_witness


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _bundle_tree_entries(bundle_root: Path) -> List[str]:
    lines: List[str] = []
    for p in sorted(bundle_root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(bundle_root)).replace("\\", "/")
        if rel == "manifest.json":
            continue
        if rel.startswith("hashes/"):
            continue
        lines.append(f"{rel}\t{_sha256_file(p)}")
    return lines


def _bundle_tree_hash(bundle_root: Path) -> str:
    blob = "\n".join(_bundle_tree_entries(bundle_root)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _manifest_hash(manifest: Dict[str, Any]) -> str:
    src = json.loads(json.dumps(dict(manifest or {}), ensure_ascii=True))
    hashes = dict(src.get("hashes") or {})
    hashes["manifest_sha256"] = ""
    src["hashes"] = hashes
    blob = json.dumps(src, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _write_sha256s(bundle_root: Path) -> None:
    items: List[str] = []
    for p in sorted(bundle_root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(bundle_root)).replace("\\", "/")
        if rel == "hashes/SHA256SUMS.txt":
            continue
        items.append(f"{_sha256_file(p)}  {rel}")
    out_path = (bundle_root / "hashes" / "SHA256SUMS.txt").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(items) + ("\n" if items else ""), encoding="utf-8")


def _refresh_manifest(bundle_root: Path, manifest_obj: Dict[str, Any], *, persist_dir: Path | None = None) -> Dict[str, Any]:
    manifest = dict(manifest_obj or {})
    hashes = dict(manifest.get("hashes") or {})
    hashes["bundle_tree_sha256"] = _bundle_tree_hash(bundle_root)
    manifest["hashes"] = hashes

    if persist_dir is not None:
        if isinstance(manifest.get("publisher_sigs"), list):
            resigned: List[Dict[str, Any]] = []
            tree_hash = str(hashes.get("bundle_tree_sha256") or "")
            for row in [dict(x) for x in list(manifest.get("publisher_sigs") or []) if isinstance(x, dict)]:
                key_id = str(row.get("key_id") or "").strip()
                if not key_id:
                    continue
                priv_path = (persist_dir / "keys" / f"{key_id}_private.pem").resolve()
                if (not priv_path.exists()) or (not priv_path.is_file()):
                    continue
                try:
                    sig = bundle_signing.sign_tree_hash(tree_hash, str(priv_path), key_id=key_id)
                except Exception:
                    continue
                resigned.append(dict(sig))
            if resigned:
                manifest["publisher_sigs"] = resigned

    _write_json((bundle_root / "manifest.json").resolve(), manifest)
    _write_sha256s(bundle_root)

    manifest = _read_json((bundle_root / "manifest.json").resolve())
    hashes = dict(manifest.get("hashes") or {})
    hashes["manifest_sha256"] = ""
    manifest["hashes"] = hashes
    hashes["manifest_sha256"] = _manifest_hash(manifest)
    manifest["hashes"] = hashes
    _write_json((bundle_root / "manifest.json").resolve(), manifest)
    (bundle_root / "hashes").mkdir(parents=True, exist_ok=True)
    (bundle_root / "hashes" / "manifest.sha256").write_text(str(hashes["manifest_sha256"]) + "\n", encoding="utf-8")
    _write_sha256s(bundle_root)
    return manifest


def _run_json(args: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    proc = subprocess.run(args, capture_output=True, text=True, env=env)
    payload: Dict[str, Any] = {}
    raw = str(proc.stdout or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = dict(parsed)
        except Exception:
            payload = {}
    payload["rc"] = int(proc.returncode)
    payload["stderr"] = str(proc.stderr or "")
    payload.setdefault("ok", bool(proc.returncode == 0))
    payload["errors"] = list(payload.get("errors") or [])
    payload["warnings"] = list(payload.get("warnings") or [])
    return payload


def _error_codes(rep: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for row in list(rep.get("errors") or []):
        if isinstance(row, dict):
            code = str(row.get("code") or "").strip()
            if code:
                out.append(code)
    return out


def _run_manage(env: Dict[str, str], args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, "-B", str((ROOT / "tools" / "publisher_roster_manage.py").resolve())] + list(args)
    return _run_json(cmd, env)


def _run_export(env: Dict[str, str], args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, "-B", str((ROOT / "tools" / "export_audit_bundle.py").resolve())] + list(args)
    return _run_json(cmd, env)


def _run_verify(env: Dict[str, str], args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, "-B", str((ROOT / "tools" / "auditor_verify_bundle.py").resolve())] + list(args)
    return _run_json(cmd, env)


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


def _build_l4w_record(persist_dir: Path, agent_id: str, event_id: str, evidence: Dict[str, str]) -> Dict[str, Any]:
    head = l4w_witness.chain_head(agent_id)
    prev_hash = str(head.get("envelope_hash") or "").strip().lower() if bool(head.get("has_head")) else ""
    built = l4w_witness.build_envelope_for_clear(
        agent_id,
        event_id,
        reviewer="tools.l4w_roster_anchor_smoke",
        summary="iter57 roster anchor smoke",
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
    if not bool(built.get("ok")):
        return {"ok": False, "stage": "build", "details": built}
    envelope = dict(built.get("envelope") or {})
    anchor = dict(envelope.get("roster_anchor") or {})
    if not anchor:
        return {"ok": False, "stage": "anchor", "details": "missing"}

    signed = l4w_witness.sign_envelope(envelope)
    if not bool(signed.get("ok")):
        return {"ok": False, "stage": "sign", "details": signed}
    written = l4w_witness.write_envelope(agent_id, dict(signed.get("envelope") or {}))
    if not bool(written.get("ok")):
        return {"ok": False, "stage": "write", "details": written}
    appended = l4w_witness.append_chain_record(
        agent_id,
        quarantine_event_id=event_id,
        envelope_id=str((dict(signed.get("envelope") or {})).get("envelope_id") or ""),
        envelope_hash=str(signed.get("envelope_hash") or ""),
        prev_hash=prev_hash,
        envelope_path=str(written.get("envelope_rel_path") or ""),
        envelope_sha256=str(written.get("envelope_sha256") or ""),
        ts=int((dict(signed.get("envelope") or {})).get("ts") or int(time.time())),
    )
    if not bool(appended.get("ok")):
        return {"ok": False, "stage": "append", "details": appended}
    return {
        "ok": True,
        "envelope_rel_path": str(written.get("envelope_rel_path") or ""),
        "envelope_hash": str(signed.get("envelope_hash") or ""),
        "anchor": anchor,
    }


def _drop_envelope_anchor(bundle_dir: Path, *, persist_dir: Path | None = None) -> Dict[str, Any]:
    chain_root = (bundle_dir / "l4w" / "chains" / "quarantine_clear").resolve()
    chain_files = sorted(chain_root.glob("*.jsonl"))
    if len(chain_files) != 1:
        return {"ok": False, "error": "chain_file_missing"}
    chain_path = chain_files[0]
    rows: List[Dict[str, Any]] = []
    for line in chain_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        if isinstance(obj, dict):
            rows.append(dict(obj))
    if len(rows) != 1:
        return {"ok": False, "error": "unexpected_chain_size"}
    row = dict(rows[0])
    old_env_hash = str(row.get("envelope_hash") or "").strip().lower()
    env_rel = str(row.get("envelope_path") or "").strip().replace("\\", "/")
    env_path = (bundle_dir / "l4w" / "envelopes" / env_rel).resolve()
    if (not env_path.exists()) or (not env_path.is_file()):
        return {"ok": False, "error": "envelope_missing"}

    env_obj = _read_json(env_path)
    env_obj.pop("roster_anchor", None)
    signed = l4w_witness.sign_envelope(env_obj)
    if not bool(signed.get("ok")):
        return {"ok": False, "error": "resign_failed", "details": signed}
    env_new = dict(signed.get("envelope") or {})
    env_path.write_text(json.dumps(env_new, ensure_ascii=True, indent=2), encoding="utf-8")
    new_env_sha = _sha256_file(env_path)
    new_env_hash = str((dict(env_new.get("chain") or {})).get("envelope_hash") or "").strip().lower()

    row["envelope_sha256"] = new_env_sha
    row["envelope_hash"] = new_env_hash
    chain_path.write_text(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="utf-8")

    idx_path = (bundle_dir / "refs" / "evidence_index.json").resolve()
    idx_obj = _read_json(idx_path)
    items = [dict(x) for x in list(idx_obj.get("items") or []) if isinstance(x, dict)]
    if items:
        for item in items:
            if str(item.get("envelope_hash") or "").strip().lower() == old_env_hash:
                item["envelope_hash"] = new_env_hash
        idx_obj["items"] = items
        _write_json(idx_path, idx_obj)

    cross_path = (bundle_dir / "refs" / "cross_refs.json").resolve()
    cross_obj = _read_json(cross_path)
    cross_items = [dict(x) for x in list(cross_obj.get("items") or []) if isinstance(x, dict)]
    if cross_items:
        for item in cross_items:
            if str(item.get("envelope_hash") or "").strip().lower() == old_env_hash:
                item["envelope_hash"] = new_env_hash
        cross_obj["items"] = cross_items
        _write_json(cross_path, cross_obj)

    manifest_path = (bundle_dir / "manifest.json").resolve()
    manifest = _read_json(manifest_path)
    head = dict(manifest.get("head") or {})
    head["last_envelope_hash"] = new_env_hash
    manifest["head"] = head
    _refresh_manifest(bundle_dir, manifest, persist_dir=persist_dir)
    return {"ok": True, "envelope_hash": new_env_hash, "envelope_sha256": new_env_sha}


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_l4w_roster_anchor_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    out_root = (tmp_root / "out").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)
    keys_dir = (persist_dir / "keys").resolve()
    keys_dir.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "ESTER_VOLITION_SLOT",
        "ESTER_BUNDLE_PUBLISHER_SIGNING",
        "ESTER_ROSTER_ROOT_PUBKEY_PATH",
        "ESTER_ROSTER_ROOT_PRIVKEY_PATH",
        "ESTER_L4W_ROSTER_ANCHOR_REQUIRED",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_BUNDLE_PUBLISHER_SIGNING"] = "1"
    os.environ["ESTER_L4W_ROSTER_ANCHOR_REQUIRED"] = "1"

    try:
        if not bool(l4w_witness.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "l4w_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        if not bool(evidence_signing.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "evidence_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2

        root_priv = (keys_dir / "roster_root_private.pem").resolve()
        root_pub = (keys_dir / "roster_root_public.pem").resolve()
        if not bool(l4w_witness.ensure_keypair(priv_path=str(root_priv), pub_path=str(root_pub), overwrite=True).get("ok")):
            print(json.dumps({"ok": False, "error": "roster_root_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        os.environ["ESTER_ROSTER_ROOT_PRIVKEY_PATH"] = str(root_priv)
        os.environ["ESTER_ROSTER_ROOT_PUBKEY_PATH"] = str(root_pub)

        pa_priv = (keys_dir / "publisher-A_private.pem").resolve()
        pa_pub = (keys_dir / "publisher-A_public.pem").resolve()
        pb_priv = (keys_dir / "publisher-B_private.pem").resolve()
        pb_pub = (keys_dir / "publisher-B_public.pem").resolve()
        for priv, pub in [(pa_priv, pa_pub), (pb_priv, pb_pub)]:
            if not bool(l4w_witness.ensure_keypair(priv_path=str(priv), pub_path=str(pub), overwrite=True).get("ok")):
                print(json.dumps({"ok": False, "error": "publisher_keypair_failed", "pub": str(pub)}, ensure_ascii=True, indent=2))
                return 2

        env = dict(os.environ)
        roster_path = (keys_dir / "publisher_roster.json").resolve()
        init_rep = _run_manage(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--op",
                "init",
                "--reason",
                "iter57_init",
                "init",
                "--out",
                str(roster_path),
                "--threshold",
                "2",
                "--of",
                "3",
                "--roster-id",
                "iter57-roster",
                "--roster-root-privkey",
                str(root_priv),
                "--roster-root-pubkey",
                str(root_pub),
            ],
        )
        add_a = _run_manage(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--op",
                "update",
                "--reason",
                "iter57_add_a",
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-A",
                "--pubkey",
                str(pa_pub),
                "--status",
                "active",
                "--roster-root-privkey",
                str(root_priv),
                "--roster-root-pubkey",
                str(root_pub),
            ],
        )
        add_b = _run_manage(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--op",
                "update",
                "--reason",
                "iter57_add_b",
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-B",
                "--pubkey",
                str(pb_pub),
                "--status",
                "active",
                "--roster-root-privkey",
                str(root_priv),
                "--roster-root-pubkey",
                str(root_pub),
            ],
        )

        agent_id = "agent_l4w_roster_anchor_smoke"
        event_id = "evt_l4w_anchor_1"
        evidence = _write_evidence_packet(
            persist_dir,
            agent_id,
            event_id,
            "tools.l4w_roster_anchor_smoke",
            "iter57 anchor envelope",
        )
        l4w_record = _build_l4w_record(persist_dir, agent_id, event_id, evidence)

        # FULL verification requires cross-layer refs and evidence files.
        drift_events_path = (persist_dir / "capability_drift" / "quarantine_events.jsonl").resolve()
        drift_events_path.parent.mkdir(parents=True, exist_ok=True)
        drift_event = {
            "type": "QUARANTINE_CLEAR",
            "ts": int(time.time()),
            "agent_id": agent_id,
            "event_id": event_id,
            "details": {
                "l4w_envelope_hash": str(l4w_record.get("envelope_hash") or ""),
                "evidence_sha256": str(evidence.get("sha256") or ""),
            },
        }
        drift_events_path.write_text(json.dumps(drift_event, ensure_ascii=True) + "\n", encoding="utf-8")

        volition_path = (persist_dir / "volition" / "decisions.jsonl").resolve()
        volition_path.parent.mkdir(parents=True, exist_ok=True)
        volition_row = {
            "ts": int(time.time()),
            "agent_id": agent_id,
            "step": "drift.quarantine.clear",
            "action_id": "drift.quarantine.clear",
            "metadata": {
                "action_id": "drift.quarantine.clear",
                "agent_id": agent_id,
                "quarantine_event_id": event_id,
                "evidence_sha256": str(evidence.get("sha256") or ""),
                "l4w_envelope_hash": str(l4w_record.get("envelope_hash") or ""),
            },
        }
        volition_path.write_text(json.dumps(volition_row, ensure_ascii=True) + "\n", encoding="utf-8")

        bundle_dir = (out_root / "bundle_anchor").resolve()
        export_rep = _run_export(
            env,
            [
                "--agent-id",
                agent_id,
                "--out",
                str(bundle_dir),
                "--profile",
                "BASE",
                "--multi-signer",
                "--publisher-roster",
                str(roster_path),
                "--pubkey-roster-root",
                str(root_pub),
                "--include-evidence-files",
                "--include-cross-refs",
                "--include-roster-log",
                "--roster-log-last",
                "10",
                "--json",
            ],
        )
        verify_full = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_dir),
                "--profile",
                "FULL",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        bundle_bad_entry = (out_root / "bundle_bad_entry").resolve()
        shutil.copytree(bundle_dir, bundle_bad_entry, dirs_exist_ok=True)
        bad_entry_manifest = _read_json((bundle_bad_entry / "manifest.json").resolve())
        bad_entry_manifest.setdefault("publisher_policy", {})["roster_entry_hash"] = "a" * 64
        _refresh_manifest(bundle_bad_entry, bad_entry_manifest, persist_dir=persist_dir)
        verify_bad_entry = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_bad_entry),
                "--profile",
                "FULL",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        bundle_bad_body = (out_root / "bundle_bad_body").resolve()
        shutil.copytree(bundle_dir, bundle_bad_body, dirs_exist_ok=True)
        bad_body_manifest = _read_json((bundle_bad_body / "manifest.json").resolve())
        bad_body_manifest.setdefault("roster_anchor", {})["body_sha256"] = "b" * 64
        _refresh_manifest(bundle_bad_body, bad_body_manifest, persist_dir=persist_dir)
        verify_bad_body = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_bad_body),
                "--profile",
                "FULL",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        bundle_no_log = (out_root / "bundle_no_log").resolve()
        shutil.copytree(bundle_dir, bundle_no_log, dirs_exist_ok=True)
        try:
            (bundle_no_log / "keys" / "publisher_roster_log.jsonl").unlink()
        except Exception:
            pass
        no_log_manifest = _read_json((bundle_no_log / "manifest.json").resolve())
        _refresh_manifest(bundle_no_log, no_log_manifest, persist_dir=persist_dir)
        verify_no_log = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_no_log),
                "--profile",
                "FULL",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        bundle_no_env_anchor = (out_root / "bundle_no_env_anchor").resolve()
        shutil.copytree(bundle_dir, bundle_no_env_anchor, dirs_exist_ok=True)
        drop_anchor_rep = _drop_envelope_anchor(bundle_no_env_anchor, persist_dir=persist_dir)
        verify_no_env_anchor_full = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_no_env_anchor),
                "--profile",
                "FULL",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )
        verify_no_env_anchor_hro = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_no_env_anchor),
                "--profile",
                "HRO",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )
        verify_no_env_anchor_base = _run_verify(
            env,
            [
                "--bundle",
                str(bundle_no_env_anchor),
                "--profile",
                "BASE",
                "--allow-missing-roster-entry-hash",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        env_a = dict(env)
        env_a["ESTER_VOLITION_SLOT"] = "A"
        bundle_slot_a = (out_root / "bundle_slot_a_no_anchor").resolve()
        export_slot_a_no_anchor = _run_export(
            env_a,
            [
                "--agent-id",
                agent_id,
                "--out",
                str(bundle_slot_a),
                "--profile",
                "BASE",
                "--multi-signer",
                "--publisher-roster",
                str(roster_path),
                "--pubkey-roster-root",
                str(root_pub),
                "--no-anchor-roster-log",
                "--json",
            ],
        )
        verify_slot_a_base_fail = _run_verify(
            env_a,
            [
                "--bundle",
                str(bundle_slot_a),
                "--profile",
                "BASE",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )
        verify_slot_a_base_allow = _run_verify(
            env_a,
            [
                "--bundle",
                str(bundle_slot_a),
                "--profile",
                "BASE",
                "--allow-missing-roster-entry-hash",
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        codes_bad_entry = _error_codes(verify_bad_entry)
        codes_bad_body = _error_codes(verify_bad_body)
        codes_no_log = _error_codes(verify_no_log)
        codes_no_env_anchor_full = _error_codes(verify_no_env_anchor_full)
        warnings_no_env_anchor_hro = list(verify_no_env_anchor_hro.get("warnings") or [])
        warnings_slot_a_allow = list(verify_slot_a_base_allow.get("warnings") or [])

        ok = (
            bool(init_rep.get("ok"))
            and bool(add_a.get("ok"))
            and bool(add_b.get("ok"))
            and bool(l4w_record.get("ok"))
            and bool(l4w_record.get("anchor"))
            and bool(export_rep.get("ok"))
            and int(verify_full.get("rc") or 0) == 0
            and int(verify_bad_entry.get("rc") or 0) == 2
            and ("ROSTER_LOG_ENTRY_NOT_FOUND" in codes_bad_entry)
            and int(verify_bad_body.get("rc") or 0) == 2
            and ("ROSTER_ANCHOR_BODY_MISMATCH" in codes_bad_body)
            and int(verify_no_log.get("rc") or 0) == 2
            and ("ROSTER_LOG_REQUIRED" in codes_no_log)
            and bool(drop_anchor_rep.get("ok"))
            and int(verify_no_env_anchor_full.get("rc") or 0) == 2
            and ("ROSTER_ENTRY_HASH_REQUIRED" in codes_no_env_anchor_full)
            and int(verify_no_env_anchor_hro.get("rc") or 0) == 0
            and any(str(dict(x).get("code") or "") == "ROSTER_ENTRY_HASH_REQUIRED" for x in warnings_no_env_anchor_hro if isinstance(x, dict))
            and int(verify_no_env_anchor_base.get("rc") or 0) in {0, 3}
            and bool(export_slot_a_no_anchor.get("ok"))
            and int(verify_slot_a_base_fail.get("rc") or 0) == 2
            and int(verify_slot_a_base_allow.get("rc") or 0) in {0, 3}
            and any(str(dict(x).get("code") or "") == "ROSTER_ENTRY_HASH_REQUIRED" for x in warnings_slot_a_allow if isinstance(x, dict))
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "init": init_rep,
            "add_a": add_a,
            "add_b": add_b,
            "l4w_record": l4w_record,
            "export": export_rep,
            "verify_full": verify_full,
            "verify_bad_entry": verify_bad_entry,
            "verify_bad_body": verify_bad_body,
            "verify_no_log": verify_no_log,
            "drop_anchor_rep": drop_anchor_rep,
            "verify_no_env_anchor_full": verify_no_env_anchor_full,
            "verify_no_env_anchor_hro": verify_no_env_anchor_hro,
            "verify_no_env_anchor_base": verify_no_env_anchor_base,
            "export_slot_a_no_anchor": export_slot_a_no_anchor,
            "verify_slot_a_base_fail": verify_slot_a_base_fail,
            "verify_slot_a_base_allow": verify_slot_a_base_allow,
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
