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
    payload: Dict[str, Any] = {}
    raw = str(proc.stdout or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
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


def _run_roster(env: Dict[str, str], args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, "-B", str((ROOT / "tools" / "publisher_roster_manage.py").resolve())] + list(args)
    return _run_json(cmd, env)


def _export(env: Dict[str, str], *, agent_id: str, out_dir: Path, roster: Path, roster_root_pub: Path, profile: str = "BASE", include_evidence: bool = False, include_disclosures: bool = False, extra: List[str] | None = None) -> Dict[str, Any]:
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
        "--multi-signer",
        "--publisher-roster",
        str(roster),
        "--pubkey-roster-root",
        str(roster_root_pub),
        "--json",
    ]
    if include_evidence:
        cmd.append("--include-evidence-files")
    if include_disclosures:
        cmd.append("--include-disclosures")
    if extra:
        cmd.extend(list(extra))
    return _run_json(cmd, env)


def _verify(env: Dict[str, str], *, bundle: Path, profile: str, roster_root_pub: Path, extra: List[str] | None = None) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        str((ROOT / "tools" / "auditor_verify_bundle.py").resolve()),
        "--bundle",
        str(bundle),
        "--profile",
        profile,
        "--pubkey-roster-root",
        str(roster_root_pub),
        "--json",
    ]
    if extra:
        cmd.extend(list(extra))
    return _run_json(cmd, env)


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
    return {"ok": True}


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_roster_multisig_smoke_")).resolve()
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
        "ESTER_PUBLISHER_ROSTER_PATH",
        "ESTER_ROSTER_ROOT_PUBKEY_PATH",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_BUNDLE_PUBLISHER_SIGNING"] = "1"

    try:
        if not bool(l4w_witness.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "l4w_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2
        if not bool(evidence_signing.ensure_keypair().get("ok")):
            print(json.dumps({"ok": False, "error": "evidence_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2

        roster_root_priv = (keys_dir / "roster_root_private.pem").resolve()
        roster_root_pub = (keys_dir / "roster_root_public.pem").resolve()
        if not bool(l4w_witness.ensure_keypair(priv_path=str(roster_root_priv), pub_path=str(roster_root_pub), overwrite=True).get("ok")):
            print(json.dumps({"ok": False, "error": "roster_root_keypair_failed"}, ensure_ascii=True, indent=2))
            return 2

        signer_ids = ["publisher-A", "publisher-B", "publisher-C", "publisher-D"]
        for signer in signer_ids:
            priv = (keys_dir / f"{signer}_private.pem").resolve()
            pub = (keys_dir / f"{signer}_public.pem").resolve()
            rep = l4w_witness.ensure_keypair(priv_path=str(priv), pub_path=str(pub), overwrite=True)
            if not bool(rep.get("ok")):
                print(json.dumps({"ok": False, "error": "publisher_keypair_failed", "key_id": signer}, ensure_ascii=True, indent=2))
                return 2

        roster_path = (keys_dir / "publisher_roster.json").resolve()
        env = dict(os.environ)
        os.environ["ESTER_PUBLISHER_ROSTER_PATH"] = str(roster_path)
        os.environ["ESTER_ROSTER_ROOT_PUBKEY_PATH"] = str(roster_root_pub)
        env = dict(os.environ)

        init_roster = _run_roster(
            env,
            [
                "init",
                "--out",
                str(roster_path),
                "--threshold",
                "2",
                "--of",
                "3",
                "--roster-id",
                "roster-smoke",
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )
        add_a = _run_roster(
            env,
            [
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-A",
                "--pubkey",
                str((keys_dir / "publisher-A_public.pem").resolve()),
                "--status",
                "active",
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )
        add_b = _run_roster(
            env,
            [
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-B",
                "--pubkey",
                str((keys_dir / "publisher-B_public.pem").resolve()),
                "--status",
                "active",
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )
        add_c = _run_roster(
            env,
            [
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-C",
                "--pubkey",
                str((keys_dir / "publisher-C_public.pem").resolve()),
                "--status",
                "active",
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )

        agent_id = "agent_l4w_roster_multisig_smoke"
        rec1 = _make_record(persist_dir, agent_id, "evt_rms_1", "tools.l4w_publisher_roster_multisig_smoke", "first")
        rec2 = _make_record(persist_dir, agent_id, "evt_rms_2", "tools.l4w_publisher_roster_multisig_smoke", "second")
        if not bool(rec1.get("ok")) or not bool(rec2.get("ok")):
            print(json.dumps({"ok": False, "error": "record_build_failed", "rec1": rec1, "rec2": rec2}, ensure_ascii=True, indent=2))
            return 2

        bundle_base = (out_root / "bundle_base").resolve()
        export_base = _export(env, agent_id=agent_id, out_dir=bundle_base, roster=roster_path, roster_root_pub=roster_root_pub, profile="BASE")
        verify_base = _verify(env, bundle=bundle_base, profile="BASE", roster_root_pub=roster_root_pub)

        bundle_hro = (out_root / "bundle_hro").resolve()
        export_hro = _export(
            env,
            agent_id=agent_id,
            out_dir=bundle_hro,
            roster=roster_path,
            roster_root_pub=roster_root_pub,
            profile="HRO",
            include_evidence=True,
            include_disclosures=False,
        )
        verify_hro = _verify(env, bundle=bundle_hro, profile="HRO", roster_root_pub=roster_root_pub)

        base_manifest = _read_json((bundle_base / "manifest.json").resolve())
        base_signers = [dict(x) for x in list(base_manifest.get("publisher_sigs") or []) if isinstance(x, dict)]
        used_key_id = str((base_signers[0] if base_signers else {}).get("key_id") or "")
        revoke_used = _run_roster(
            env,
            [
                "revoke-key",
                "--roster",
                str(roster_path),
                "--key-id",
                used_key_id,
                "--revoked-ts",
                str(int(base_manifest.get("created_ts") or int(time.time()))),
                "--reason",
                "smoke_revoke",
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )
        verify_revoked = _verify(
            env,
            bundle=bundle_base,
            profile="BASE",
            roster_root_pub=roster_root_pub,
            extra=["--publisher-roster", str(roster_path)],
        )

        retire_a = _run_roster(
            env,
            [
                "retire-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-A",
                "--not-after-ts",
                str(max(1, int(time.time()) - 1)),
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )
        add_d = _run_roster(
            env,
            [
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-D",
                "--pubkey",
                str((keys_dir / "publisher-D_public.pem").resolve()),
                "--status",
                "active",
                "--roster-root-privkey",
                str(roster_root_priv),
                "--roster-root-pubkey",
                str(roster_root_pub),
            ],
        )
        bundle_rotated = (out_root / "bundle_rotated").resolve()
        export_rotated = _export(env, agent_id=agent_id, out_dir=bundle_rotated, roster=roster_path, roster_root_pub=roster_root_pub, profile="BASE")
        verify_rotated = _verify(env, bundle=bundle_rotated, profile="BASE", roster_root_pub=roster_root_pub)
        rotated_manifest = _read_json((bundle_rotated / "manifest.json").resolve())
        rotated_signers = [str(dict(x).get("key_id") or "") for x in list(rotated_manifest.get("publisher_sigs") or []) if isinstance(x, dict)]

        bundle_fail_1of3 = (out_root / "bundle_fail_1of3").resolve()
        export_fail_1of3 = _export(
            env,
            agent_id=agent_id,
            out_dir=bundle_fail_1of3,
            roster=roster_path,
            roster_root_pub=roster_root_pub,
            profile="BASE",
            extra=["--signer-ids", "publisher-B", "--threshold", "2", "--of", "3"],
        )

        bundle_dup = (out_root / "bundle_dup").resolve()
        shutil.copytree(bundle_rotated, bundle_dup, dirs_exist_ok=True)
        dup_manifest = _read_json((bundle_dup / "manifest.json").resolve())
        dup_sigs = [dict(x) for x in list(dup_manifest.get("publisher_sigs") or []) if isinstance(x, dict)]
        if dup_sigs:
            dup_manifest["publisher_sigs"] = [dup_sigs[0], dup_sigs[0]]
            dup_manifest = _refresh_manifest(bundle_dup, dup_manifest)
        verify_dup = _verify(env, bundle=bundle_dup, profile="BASE", roster_root_pub=roster_root_pub)

        revoked_codes = _error_codes(verify_revoked)
        fail_1of3_codes = _error_codes(export_fail_1of3)
        fail_1of3_error_code = str(export_fail_1of3.get("error_code") or "")
        dup_codes = _error_codes(verify_dup)
        base_policy = dict(base_manifest.get("publisher_policy") or {})

        ok = (
            bool(init_roster.get("ok"))
            and bool(add_a.get("ok"))
            and bool(add_b.get("ok"))
            and bool(add_c.get("ok"))
            and bool(export_base.get("ok"))
            and len(base_signers) >= 2
            and bool(base_policy)
            and int(verify_base.get("rc") or 0) == 0
            and bool(export_hro.get("ok"))
            and int(verify_hro.get("rc") or 0) == 0
            and bool(revoke_used.get("ok"))
            and int(verify_revoked.get("rc") or 0) == 2
            and ("ROSTER_KEY_REVOKED" in revoked_codes)
            and bool(retire_a.get("ok"))
            and bool(add_d.get("ok"))
            and bool(export_rotated.get("ok"))
            and int(verify_rotated.get("rc") or 0) == 0
            and ("publisher-A" not in rotated_signers)
            and {"publisher-B", "publisher-C", "publisher-D"}.issubset(set(rotated_signers))
            and int(export_fail_1of3.get("rc") or 0) == 2
            and ("MULTISIG_THRESHOLD_NOT_MET" in fail_1of3_codes or fail_1of3_error_code == "MULTISIG_THRESHOLD_NOT_MET")
            and int(verify_dup.get("rc") or 0) == 2
            and ("MULTISIG_THRESHOLD_NOT_MET" in dup_codes)
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "agent_id": agent_id,
            "roster": {
                "init": init_roster,
                "add_a": add_a,
                "add_b": add_b,
                "add_c": add_c,
                "revoke_used": revoke_used,
                "retire_a": retire_a,
                "add_d": add_d,
            },
            "export_base": export_base,
            "verify_base": verify_base,
            "export_hro": export_hro,
            "verify_hro": verify_hro,
            "verify_revoked": verify_revoked,
            "export_rotated": export_rotated,
            "verify_rotated": verify_rotated,
            "export_fail_1of3": export_fail_1of3,
            "verify_dup": verify_dup,
            "rotated_signers": rotated_signers,
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
