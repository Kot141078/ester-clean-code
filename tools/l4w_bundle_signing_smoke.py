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


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _manifest_hash(manifest: Dict[str, Any]) -> str:
    src = json.loads(json.dumps(dict(manifest or {}), ensure_ascii=True))
    hashes = dict(src.get("hashes") or {})
    hashes["manifest_sha256"] = ""
    src["hashes"] = hashes
    blob = json.dumps(src, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


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


def _refresh_manifest(bundle_root: Path, manifest_obj: Dict[str, Any]) -> Dict[str, Any]:
    manifest = dict(manifest_obj or {})
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


def _warn_codes(rep: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for row in list(rep.get("warnings") or []):
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
    _write_json(evidence_path, dict(signed.get("packet") or {}))
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
    sign_env = l4w_witness.sign_envelope(dict(built.get("envelope") or {}))
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
    return {
        "ok": True,
        "event_id": event_id,
        "envelope_rel": str(write_env.get("envelope_rel_path") or ""),
    }


def _export(env: Dict[str, str], agent_id: str, out_dir: Path, *, with_zip: bool = False) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str((ROOT / "tools" / "export_audit_bundle.py").resolve()),
        "--agent-id",
        agent_id,
        "--out",
        str(out_dir),
        "--sign-publisher",
        "--include-publisher-pubkey",
        "--json",
    ]
    if with_zip:
        cmd.append("--zip")
    return _run_json(cmd, env)


def _verify(env: Dict[str, str], bundle: Path, profile: str, *, allow_missing: bool = False) -> Dict[str, Any]:
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
    if allow_missing:
        cmd.append("--allow-missing-publisher-sig")
    return _run_json(cmd, env)


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_l4w_bundle_sign_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    out_root = (tmp_root / "out").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    out_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "ESTER_VOLITION_SLOT",
        "ESTER_BUNDLE_PUBLISHER_PRIVKEY_PATH",
        "ESTER_BUNDLE_PUBLISHER_PUBKEY_PATH",
        "ESTER_BUNDLE_PUBLISHER_KEY_ID",
        "ESTER_BUNDLE_PUBLISHER_SIGNING",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_BUNDLE_PUBLISHER_SIGNING"] = "1"
    os.environ["ESTER_BUNDLE_PUBLISHER_KEY_ID"] = "publisher-default"

    try:
        if not bool(l4w_witness.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "l4w_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        if not bool(evidence_signing.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "evidence_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2

        publisher_priv = (persist_dir / "keys" / "publisher_ed25519_private.pem").resolve()
        publisher_pub = (persist_dir / "keys" / "publisher_ed25519_public.pem").resolve()
        if not bool(l4w_witness.ensure_keypair(priv_path=str(publisher_priv), pub_path=str(publisher_pub), overwrite=True).get("ok")):
            print(json.dumps({"ok": False, "error": "publisher_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        os.environ["ESTER_BUNDLE_PUBLISHER_PRIVKEY_PATH"] = str(publisher_priv)
        os.environ["ESTER_BUNDLE_PUBLISHER_PUBKEY_PATH"] = str(publisher_pub)

        agent_id = "agent_l4w_bundle_signing_smoke"
        rec1 = _make_record(persist_dir, agent_id, "evt_sign_1", "tools.l4w_bundle_signing_smoke", "first")
        rec2 = _make_record(persist_dir, agent_id, "evt_sign_2", "tools.l4w_bundle_signing_smoke", "second")
        if not bool(rec1.get("ok")) or not bool(rec2.get("ok")):
            print(json.dumps({"ok": False, "error": "records_failed", "rec1": rec1, "rec2": rec2}, ensure_ascii=True, indent=2))
            return 2

        env = dict(os.environ)
        signed_dir = (out_root / "bundle_signed").resolve()
        export_signed = _export(env, agent_id, signed_dir, with_zip=False)
        verify_base = _verify(env, signed_dir, "BASE")

        signed_zip_dir = (out_root / "bundle_signed_zip").resolve()
        export_zip = _export(env, agent_id, signed_zip_dir, with_zip=True)
        zip_path = Path(str(export_zip.get("bundle_zip") or "")).resolve()
        verify_zip = _verify(env, zip_path, "BASE")

        manifest_path = (signed_dir / "manifest.json").resolve()
        manifest_obj = _read_json(manifest_path)
        tampered_manifest = dict(manifest_obj)
        psig = dict(tampered_manifest.get("publisher_sig") or {})
        sig_b64 = str(psig.get("sig_b64") or "")
        if sig_b64:
            psig["sig_b64"] = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
            tampered_manifest["publisher_sig"] = psig
            tampered_manifest = _refresh_manifest(signed_dir, tampered_manifest)
        verify_sig_tampered = _verify(env, signed_dir, "BASE")

        removed_manifest = _read_json(manifest_path)
        removed_manifest.pop("publisher_sig", None)
        removed_manifest = _refresh_manifest(signed_dir, removed_manifest)
        verify_base_missing = _verify(env, signed_dir, "BASE")
        verify_base_missing_allowed = _verify(env, signed_dir, "BASE", allow_missing=True)
        verify_hro_missing = _verify(env, signed_dir, "HRO", allow_missing=True)
        verify_full_missing = _verify(env, signed_dir, "FULL", allow_missing=True)

        tree_tamper_dir = (out_root / "bundle_tree_tamper").resolve()
        export_tree_tamper = _export(env, agent_id, tree_tamper_dir, with_zip=False)
        tamper_env = (tree_tamper_dir / "l4w" / "envelopes" / str(rec2.get("envelope_rel") or "")).resolve()
        env_obj = _read_json(tamper_env)
        if env_obj:
            claim = dict(env_obj.get("claim") or {})
            claim["decision"] = "CLEAR_QUARANTINE_TREE_TAMPER"
            env_obj["claim"] = claim
            _write_json(tamper_env, env_obj)
        verify_tree_tampered = _verify(env, tree_tamper_dir, "BASE")

        sig_tamper_codes = _error_codes(verify_sig_tampered)
        missing_base_codes = _error_codes(verify_base_missing)
        missing_base_warn = _warn_codes(verify_base_missing_allowed)
        missing_hro_codes = _error_codes(verify_hro_missing)
        missing_full_codes = _error_codes(verify_full_missing)
        tree_tamper_codes = _error_codes(verify_tree_tampered)

        ok = (
            bool(export_signed.get("ok"))
            and bool(export_signed.get("publisher_sig_present"))
            and int(verify_base.get("rc") or 0) == 0
            and bool(export_zip.get("ok"))
            and zip_path.exists()
            and int(verify_zip.get("rc") or 0) == 0
            and int(verify_sig_tampered.get("rc") or 0) == 2
            and ("PUBLISHER_SIG_INVALID" in sig_tamper_codes)
            and int(verify_base_missing.get("rc") or 0) == 2
            and ("PUBLISHER_SIG_REQUIRED" in missing_base_codes)
            and int(verify_base_missing_allowed.get("rc") or 0) == 3
            and ("PUBLISHER_SIG_REQUIRED" in missing_base_warn)
            and int(verify_hro_missing.get("rc") or 0) == 2
            and ("PUBLISHER_SIG_REQUIRED" in missing_hro_codes)
            and int(verify_full_missing.get("rc") or 0) == 2
            and ("PUBLISHER_SIG_REQUIRED" in missing_full_codes)
            and bool(export_tree_tamper.get("ok"))
            and int(verify_tree_tampered.get("rc") or 0) == 2
            and ("BUNDLE_TREE_HASH_MISMATCH" in tree_tamper_codes)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "export_signed": export_signed,
            "verify_base": verify_base,
            "export_zip": export_zip,
            "verify_zip": verify_zip,
            "verify_sig_tampered": verify_sig_tampered,
            "verify_base_missing": verify_base_missing,
            "verify_base_missing_allowed": verify_base_missing_allowed,
            "verify_hro_missing": verify_hro_missing,
            "verify_full_missing": verify_full_missing,
            "verify_tree_tampered": verify_tree_tampered,
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
