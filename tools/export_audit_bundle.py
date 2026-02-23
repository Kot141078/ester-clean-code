# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import bundle_signing, l4w_witness, publisher_roster, publisher_transparency_log


def _sha256_bytes(blob: bytes) -> str:
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


def _is_sha256(value: str) -> bool:
    s = str(value or "").strip().lower()
    return len(s) == 64 and all(ch in "0123456789abcdef" for ch in s)


def _env_bool(name: str, default: bool) -> bool:
    raw_default = "1" if bool(default) else "0"
    raw = str(os.getenv(name, raw_default) or raw_default).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _safe_agent_file(agent_id: str) -> str:
    raw = str(agent_id or "").strip()
    if not raw:
        raw = "unknown"
    out = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in raw)
    if not out:
        out = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return out


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _read_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists() or not path.is_file():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(dict(obj))
    return rows


def _find_log_entry(entries: List[Dict[str, Any]], entry_hash: str) -> Tuple[Dict[str, Any], int]:
    target = str(entry_hash or "").strip().lower()
    if (not target) or (not _is_sha256(target)):
        return {}, -1
    for idx, row in enumerate(entries):
        if str(dict(row).get("entry_hash") or "").strip().lower() == target:
            return dict(row), idx
    return {}, -1


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _resolve_in_root(root: Path, raw_rel: str) -> Path:
    rel = str(raw_rel or "").strip().replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return (root / rel).resolve()


def _manifest_hash(manifest: Dict[str, Any]) -> str:
    src = json.loads(json.dumps(dict(manifest or {}), ensure_ascii=True))
    hashes = dict(src.get("hashes") or {})
    hashes["manifest_sha256"] = ""
    src["hashes"] = hashes
    return _sha256_bytes(json.dumps(src, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def _bundle_tree_entries(bundle_root: Path) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for p in sorted(bundle_root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(bundle_root)).replace("\\", "/")
        if rel == "manifest.json":
            continue
        if rel.startswith("hashes/"):
            continue
        out.append((rel, _sha256_file(p)))
    return out


def _bundle_tree_hash(bundle_root: Path) -> str:
    entries = _bundle_tree_entries(bundle_root)
    lines = [f"{rel}\t{sha}" for rel, sha in entries]
    blob = ("\n".join(lines)).encode("utf-8")
    return _sha256_bytes(blob)


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


def _pub_fingerprint(pub_path: Path) -> str:
    if not pub_path.exists():
        return ""
    return bundle_signing.pub_fingerprint_from_path(str(pub_path))


def _default_pub_paths(persist_dir: Path) -> Tuple[Path, Path]:
    raw_l4w = str(os.getenv("ESTER_L4W_SIGNING_PUBKEY_PATH") or "").strip()
    raw_ev = str(os.getenv("ESTER_EVIDENCE_SIGNING_PUBKEY_PATH") or "").strip()

    if raw_l4w:
        p = Path(raw_l4w)
        l4w_pub = p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    else:
        l4w_pub = (persist_dir / "keys" / "evidence_ed25519_public.pem").resolve()

    if raw_ev:
        p = Path(raw_ev)
        ev_pub = p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    else:
        ev_pub = (persist_dir / "keys" / "evidence_ed25519_public.pem").resolve()
    return l4w_pub, ev_pub


def _default_sign_paths(persist_dir: Path) -> Tuple[Path, Path]:
    raw_priv = str(os.getenv("ESTER_BUNDLE_PUBLISHER_PRIVKEY_PATH") or "").strip()
    raw_pub = str(os.getenv("ESTER_BUNDLE_PUBLISHER_PUBKEY_PATH") or "").strip()
    if raw_priv:
        p = Path(raw_priv)
        priv = p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    else:
        priv = (persist_dir / "keys" / "evidence_ed25519_private.pem").resolve()
    if raw_pub:
        p = Path(raw_pub)
        pub = p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    else:
        pub = (persist_dir / "keys" / "evidence_ed25519_public.pem").resolve()
    return priv, pub


def _safe_env_key_id(key_id: str) -> str:
    raw = str(key_id or "").strip().upper()
    out = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "PUBLISHER_DEFAULT"


def _resolve_signer_priv_path(persist_dir: Path, key_id: str) -> Path:
    env_name = f"ESTER_PUBLISHER_PRIVKEY_{_safe_env_key_id(key_id)}"
    raw_env = str(os.getenv(env_name) or "").strip()
    if raw_env:
        p = Path(raw_env)
        return p.resolve() if p.is_absolute() else (persist_dir / p).resolve()
    return (persist_dir / "keys" / f"{key_id}_private.pem").resolve()


def _resolve_roster_path(persist_dir: Path, cli_path: str) -> Tuple[Path, bool]:
    if str(cli_path or "").strip():
        p = Path(str(cli_path or "").strip())
        return (p.resolve() if p.is_absolute() else (persist_dir / p).resolve(), True)
    env_path = str(os.getenv("ESTER_PUBLISHER_ROSTER_PATH") or "").strip()
    if env_path:
        p = Path(env_path)
        return (p.resolve() if p.is_absolute() else (persist_dir / p).resolve(), False)
    return ((persist_dir / "keys" / "publisher_roster.json").resolve(), False)


def _resolve_roster_root_pubkey_path(persist_dir: Path, cli_path: str) -> Tuple[Path, bool]:
    if str(cli_path or "").strip():
        p = Path(str(cli_path or "").strip())
        return (p.resolve() if p.is_absolute() else (persist_dir / p).resolve(), True)
    env_path = str(os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "").strip()
    if env_path:
        p = Path(env_path)
        return (p.resolve() if p.is_absolute() else (persist_dir / p).resolve(), False)
    return (Path(""), False)


def _parse_signer_ids(raw: str) -> List[str]:
    out: List[str] = []
    seen: Dict[str, bool] = {}
    for item in str(raw or "").split(","):
        key_id = str(item or "").strip()
        if not key_id:
            continue
        if seen.get(key_id):
            continue
        seen[key_id] = True
        out.append(key_id)
    return out


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _find_drift_match(events: List[Dict[str, Any]], *, agent_id: str, event_id: str, envelope_hash: str, evidence_sha: str) -> Dict[str, Any]:
    for row in events:
        if str(row.get("type") or "") != "QUARANTINE_CLEAR":
            continue
        if str(row.get("agent_id") or "") != agent_id:
            continue
        if str(row.get("event_id") or "") != event_id:
            continue
        details = dict(row.get("details") or {})
        e_hash = str(details.get("l4w_envelope_hash") or "").strip().lower()
        e_sha = str(details.get("evidence_sha256") or "").strip().lower()
        if e_hash == envelope_hash and e_sha == evidence_sha:
            return {"found": True, "ts": int(row.get("ts") or 0)}
    return {"found": False, "ts": 0}


def _extract_meta_ref(metadata: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    src = dict(metadata or {})
    for key in keys:
        raw = str(src.get(key) or "").strip().lower()
        if raw:
            return raw
    return ""


def _find_volition_match(rows: List[Dict[str, Any]], *, agent_id: str, event_id: str, envelope_hash: str, evidence_sha: str) -> Dict[str, Any]:
    for row in rows:
        step = str(row.get("step") or "").strip().lower()
        action_id = str(row.get("action_id") or "").strip().lower()
        metadata = dict(row.get("metadata") or {})
        meta_action = str(metadata.get("action_id") or "").strip().lower()
        if step != "drift.quarantine.clear" and action_id != "drift.quarantine.clear" and meta_action != "drift.quarantine.clear":
            continue
        j_agent = str(row.get("agent_id") or metadata.get("agent_id") or "").strip()
        if j_agent and j_agent != agent_id:
            continue
        j_event = str(metadata.get("quarantine_event_id") or row.get("event_id") or "").strip()
        if j_event and j_event != event_id:
            continue
        j_sha = _extract_meta_ref(metadata, ("evidence_sha256", "evidence_hash"))
        j_l4w = _extract_meta_ref(metadata, ("l4w_envelope_hash", "l4w_hash", "l4w_envelope_sha256"))
        if j_sha == evidence_sha and j_l4w == envelope_hash:
            return {"found": True, "ts": int(row.get("ts") or 0)}
    return {"found": False, "ts": 0}


def main() -> int:
    ap = argparse.ArgumentParser(description="Export L4W auditor bundle (directory + optional zip)")
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--profile", default="BASE")
    ap.add_argument("--include-disclosures", action="store_true")
    ap.add_argument("--include-evidence-files", action="store_true")
    ap.add_argument("--include-cross-refs", action="store_true")
    ap.add_argument("--max-records", type=int, default=0)
    ap.add_argument("--persist-dir", default="")
    ap.add_argument("--sign-publisher", action="store_true")
    ap.add_argument("--no-sign-publisher", action="store_true")
    ap.add_argument("--publisher-privkey", default="")
    ap.add_argument("--publisher-pubkey", default="")
    ap.add_argument("--publisher-key-id", default="")
    ap.add_argument("--include-publisher-pubkey", action="store_true")
    ap.add_argument("--publisher-roster", default="")
    ap.add_argument("--pubkey-roster-root", default="")
    ap.add_argument("--multi-signer", action="store_true")
    ap.add_argument("--threshold", type=int, default=0)
    ap.add_argument("--of", type=int, default=0)
    ap.add_argument("--signer-ids", default="")
    ap.add_argument("--allow-legacy-single-sig", action="store_true")
    ap.add_argument("--include-roster-log", action="store_true")
    ap.add_argument("--roster-log-last", type=int, default=20)
    ap.add_argument("--roster-entry-hash", default="")
    ap.add_argument("--anchor-roster-log", action="store_true")
    ap.add_argument("--no-anchor-roster-log", action="store_true")
    ap.add_argument("--require-roster-log", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    aid = str(ns.agent_id or "").strip()
    if not aid:
        print(json.dumps({"ok": False, "error": "agent_id_required"}, ensure_ascii=True, indent=2))
        return 2
    profile = str(ns.profile or "BASE").strip().upper()
    if profile not in {"BASE", "HRO", "FULL"}:
        print(json.dumps({"ok": False, "error": "profile_invalid"}, ensure_ascii=True, indent=2))
        return 2

    slot = _slot()
    sign_env_default = _env_bool("ESTER_BUNDLE_PUBLISHER_SIGNING", True)
    signing_enabled = bool(sign_env_default)
    if bool(ns.sign_publisher):
        signing_enabled = True
    if bool(ns.no_sign_publisher):
        signing_enabled = False
    include_publisher_pubkey = bool(ns.include_publisher_pubkey) or bool(signing_enabled)
    publisher_key_id = str(
        ns.publisher_key_id
        or os.getenv("ESTER_BUNDLE_PUBLISHER_KEY_ID")
        or "publisher-default"
    ).strip() or "publisher-default"
    allow_legacy_single_sig = bool(ns.allow_legacy_single_sig) and slot == "A"
    roster_entry_override = str(ns.roster_entry_hash or "").strip().lower()

    persist = Path(str(ns.persist_dir or "").strip()).resolve() if str(ns.persist_dir or "").strip() else Path(str(os.getenv("PERSIST_DIR") or (ROOT / "data"))).resolve()
    if not persist.exists():
        print(json.dumps({"ok": False, "error": "persist_dir_not_found", "persist_dir": str(persist)}, ensure_ascii=True, indent=2))
        return 2

    default_sign_priv, default_sign_pub = _default_sign_paths(persist)
    if str(ns.publisher_privkey or "").strip():
        p = Path(str(ns.publisher_privkey or "").strip())
        publisher_priv = p.resolve() if p.is_absolute() else (persist / p).resolve()
    else:
        publisher_priv = default_sign_priv
    if str(ns.publisher_pubkey or "").strip():
        p = Path(str(ns.publisher_pubkey or "").strip())
        publisher_pub = p.resolve() if p.is_absolute() else (persist / p).resolve()
    else:
        publisher_pub = default_sign_pub

    parsed_signer_ids = _parse_signer_ids(str(ns.signer_ids or ""))
    roster_path, roster_path_explicit = _resolve_roster_path(persist, str(ns.publisher_roster or ""))
    roster_root_pubkey, roster_root_pubkey_explicit = _resolve_roster_root_pubkey_path(persist, str(ns.pubkey_roster_root or ""))
    roster_present = roster_path.exists() and roster_path.is_file()
    multi_signer_requested = bool(ns.multi_signer) or bool(parsed_signer_ids) or int(ns.threshold or 0) > 0 or int(ns.of or 0) > 0
    multi_signer_enabled = bool(signing_enabled) and bool(multi_signer_requested or roster_present)

    out_dir = Path(str(ns.out or "").strip()).resolve()
    if out_dir.exists():
        if not out_dir.is_dir():
            print(json.dumps({"ok": False, "error": "out_not_directory", "out": str(out_dir)}, ensure_ascii=True, indent=2))
            return 2
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_root = out_dir
    chain_src = (persist / "l4w" / "chains" / "quarantine_clear" / f"{_safe_agent_file(aid)}.jsonl").resolve()
    envelopes_root = (persist / "l4w" / "envelopes").resolve()
    evidence_root = (persist / "capability_drift" / "evidence").resolve()
    disclosures_root = (persist / "l4w" / "disclosures").resolve()
    volition_path = (persist / "volition" / "decisions.jsonl").resolve()
    events_path = (persist / "capability_drift" / "quarantine_events.jsonl").resolve()

    if not _path_within(chain_src, persist) or not _path_within(envelopes_root, persist) or not _path_within(evidence_root, persist):
        print(json.dumps({"ok": False, "error": "path_forbidden"}, ensure_ascii=True, indent=2))
        return 2

    rows: List[Dict[str, Any]] = []
    if chain_src.exists():
        with chain_src.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(dict(obj))
    if int(ns.max_records or 0) > 0:
        rows = rows[-max(1, int(ns.max_records or 0)) :]

    chain_dst = (bundle_root / "l4w" / "chains" / "quarantine_clear" / f"{_safe_agent_file(aid)}.jsonl").resolve()
    chain_dst.parent.mkdir(parents=True, exist_ok=True)
    with chain_dst.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=True, separators=(",", ":")) + "\n")

    evidence_items: List[Dict[str, Any]] = []
    events_rows: List[Dict[str, Any]] = []
    volition_rows: List[Dict[str, Any]] = []
    if bool(ns.include_cross_refs) and events_path.exists():
        with events_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    events_rows.append(dict(obj))
    if bool(ns.include_cross_refs) and volition_path.exists():
        with volition_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    volition_rows.append(dict(obj))

    for row in rows:
        env_rel = str(row.get("envelope_path") or "").strip().replace("\\", "/")
        env_src = _resolve_in_root(envelopes_root, env_rel)
        if (not _path_within(env_src, envelopes_root)) or (not env_src.exists()) or (not env_src.is_file()):
            continue
        env_dst = (bundle_root / "l4w" / "envelopes" / env_rel).resolve()
        if not _path_within(env_dst, bundle_root):
            continue
        _copy_file(env_src, env_dst)
        env_obj = _read_json(env_src)
        env_hash = str((dict(env_obj.get("chain") or {})).get("envelope_hash") or "").strip().lower()
        subj = dict(env_obj.get("subject") or {})
        event_id = str(subj.get("quarantine_event_id") or row.get("quarantine_event_id") or "")
        eref = dict(env_obj.get("evidence_ref") or {})
        ev_rel = str(eref.get("path") or "").strip().replace("\\", "/")
        ev_sha = str(eref.get("sha256") or "").strip().lower()
        ev_schema = str(eref.get("evidence_schema") or "")
        ev_payload_hash = str(eref.get("evidence_payload_hash") or "")
        item: Dict[str, Any] = {
            "quarantine_event_id": event_id,
            "envelope_hash": env_hash,
            "evidence": {
                "path": ev_rel,
                "sha256": ev_sha,
                "evidence_schema": ev_schema,
                "evidence_payload_hash": ev_payload_hash,
            },
            "has_evidence_file_in_bundle": False,
        }
        if bool(ns.include_evidence_files):
            ev_src = _resolve_in_root(evidence_root, ev_rel)
            if _path_within(ev_src, evidence_root) and ev_src.exists() and ev_src.is_file():
                ev_dst = (bundle_root / "refs" / "evidence_files" / ev_rel).resolve()
                if _path_within(ev_dst, bundle_root):
                    _copy_file(ev_src, ev_dst)
                    item["has_evidence_file_in_bundle"] = True
                    item["bundle_path"] = str(ev_dst.relative_to(bundle_root)).replace("\\", "/")
        evidence_items.append(item)

        if bool(ns.include_disclosures) and _is_sha256(env_hash):
            dis_src = (disclosures_root / f"{env_hash}.json").resolve()
            if _path_within(dis_src, disclosures_root) and dis_src.exists() and dis_src.is_file():
                dis_dst = (bundle_root / "l4w" / "disclosures" / f"{env_hash}.json").resolve()
                _copy_file(dis_src, dis_dst)

    _write_json(
        (bundle_root / "refs" / "evidence_index.json").resolve(),
        {
            "schema": "ester.l4w.evidence_index.v1",
            "agent_id": aid,
            "items": evidence_items,
        },
    )

    if bool(ns.include_cross_refs):
        cross_items: List[Dict[str, Any]] = []
        for item in evidence_items:
            event_id = str(item.get("quarantine_event_id") or "")
            env_hash = str(item.get("envelope_hash") or "").lower()
            ev_sha = str((dict(item.get("evidence") or {})).get("sha256") or "").lower()
            cross_items.append(
                {
                    "quarantine_event_id": event_id,
                    "envelope_hash": env_hash,
                    "evidence_sha256": ev_sha,
                    "drift_event": _find_drift_match(events_rows, agent_id=aid, event_id=event_id, envelope_hash=env_hash, evidence_sha=ev_sha),
                    "volition": _find_volition_match(volition_rows, agent_id=aid, event_id=event_id, envelope_hash=env_hash, evidence_sha=ev_sha),
                }
            )
        _write_json(
            (bundle_root / "refs" / "cross_refs.json").resolve(),
            {
                "schema": "ester.l4w.cross_refs.v1",
                "agent_id": aid,
                "items": cross_items,
            },
        )

    notes_readme = (
        "# Audit Bundle\n\n"
        "Run verifier:\n\n"
        "python -B tools/auditor_verify_bundle.py --bundle <dir-or-zip> --profile BASE --json\n\n"
        "Verifier checks publisher signature(s) over bundle_tree_sha256 and roster policy if present.\n"
    )
    notes_profile = (
        "# Profiles in Bundle Context\n\n"
        "- BASE: chain + envelope hashes/signatures + refs consistency.\n"
        "- HRO: BASE + evidence signature/payload hash (needs evidence files unless allow flag).\n"
        "- FULL: HRO + cross-layer refs (cross_refs.json or external events/volition paths).\n"
    )
    (bundle_root / "notes").mkdir(parents=True, exist_ok=True)
    (bundle_root / "notes" / "README_AUDIT.md").write_text(notes_readme, encoding="utf-8")
    (bundle_root / "notes" / "PROFILE.md").write_text(notes_profile, encoding="utf-8")

    l4w_pub, ev_pub = _default_pub_paths(persist)
    keys_dir = (bundle_root / "keys").resolve()
    keys_dir.mkdir(parents=True, exist_ok=True)
    if l4w_pub.exists() and l4w_pub.is_file():
        _copy_file(l4w_pub, (keys_dir / "l4w_public.pem").resolve())
    if ev_pub.exists() and ev_pub.is_file():
        _copy_file(ev_pub, (keys_dir / "evidence_public.pem").resolve())

    created_ts = int(time.time())
    export_warnings: List[str] = []

    publisher_pub_bundle = (keys_dir / "publisher_public.pem").resolve()
    publisher_sig: Dict[str, Any] = {}
    publisher_sigs: List[Dict[str, Any]] = []
    publisher_policy: Dict[str, Any] = {}
    publisher_fp = ""
    tree_hash = ""
    multisig_threshold = 1
    multisig_signers: List[Dict[str, Any]] = []
    roster_log_included = False
    roster_log_entries = 0
    roster_log_head_hash = ""
    roster_log_required = False
    roster_anchor_required = False
    roster_anchor: Dict[str, Any] = {}
    roster_anchor_entry_hash = ""
    roster_anchor_log_rows: List[Dict[str, Any]] = []
    roster_anchor_index = -1

    use_multisig = bool(multi_signer_enabled)
    multisig_error = ""
    if use_multisig:
        if not bundle_signing.is_available():
            multisig_error = "ED25519_UNAVAILABLE"
        elif (not roster_present) and (not multi_signer_requested):
            use_multisig = False
        elif not roster_present:
            multisig_error = "ROSTER_REQUIRED"
        elif (not roster_path_explicit) and (not _path_within(roster_path, persist)):
            multisig_error = "ROSTER_PATH_FORBIDDEN"
        elif (not roster_root_pubkey) or (not str(roster_root_pubkey)):
            multisig_error = "ROSTER_ROOT_PUBKEY_REQUIRED"
        elif (not roster_root_pubkey_explicit) and (not _path_within(roster_root_pubkey, persist)):
            multisig_error = "ROSTER_ROOT_PUBKEY_PATH_FORBIDDEN"

        roster_obj: Dict[str, Any] = {}
        roster_body_sha = ""
        if not multisig_error and use_multisig:
            loaded = publisher_roster.load_roster(str(roster_path))
            if not bool(loaded.get("ok")):
                multisig_error = str(loaded.get("error_code") or "ROSTER_REQUIRED")
            else:
                roster_obj = publisher_roster.normalize_roster(dict(loaded.get("roster") or {}))
                verify_roster = publisher_roster.verify_roster_sig(roster_obj, str(roster_root_pubkey))
                if not bool(verify_roster.get("ok")):
                    multisig_error = str(verify_roster.get("error_code") or "ROSTER_SIG_INVALID")
                else:
                    roster_body_sha = str(verify_roster.get("body_sha256") or "")
                    roster_policy = dict(roster_obj.get("policy") or {})
                    threshold = _to_int(ns.threshold if int(ns.threshold or 0) > 0 else roster_policy.get("threshold"), 2)
                    of_count = _to_int(ns.of if int(ns.of or 0) > 0 else roster_policy.get("of"), 3)
                    threshold = max(1, threshold)
                    of_count = max(1, of_count)
                    multisig_threshold = int(threshold)
                    if threshold > of_count:
                        multisig_error = "MULTISIG_THRESHOLD_NOT_MET"
                    else:
                        key_rows = [dict(x) for x in list(roster_obj.get("keys") or []) if isinstance(x, dict)]
                        key_rows = sorted(key_rows, key=lambda row: str(row.get("key_id") or ""))
                        active_ids: List[str] = []
                        by_key_id: Dict[str, Dict[str, Any]] = {}
                        for row in key_rows:
                            key_id = str(row.get("key_id") or "").strip()
                            if not key_id:
                                continue
                            by_key_id[key_id] = dict(row)
                            active_rep = publisher_roster.is_key_active_at(row, created_ts)
                            if bool(active_rep.get("ok")):
                                active_ids.append(key_id)

                        selected_ids: List[str] = []
                        if parsed_signer_ids:
                            selected_ids = list(parsed_signer_ids)
                        else:
                            selected_ids = active_ids[:of_count]

                        selected_unique: List[str] = []
                        seen_sel: Dict[str, bool] = {}
                        for key_id in selected_ids:
                            if seen_sel.get(key_id):
                                continue
                            seen_sel[key_id] = True
                            selected_unique.append(key_id)
                        selected_ids = selected_unique

                        prep_errors: List[str] = []
                        for key_id in selected_ids:
                            key_row = by_key_id.get(key_id) or {}
                            if not key_row:
                                prep_errors.append(f"{key_id}:ROSTER_KEY_UNKNOWN")
                                continue
                            active_rep = publisher_roster.is_key_active_at(key_row, created_ts)
                            if not bool(active_rep.get("ok")):
                                prep_errors.append(f"{key_id}:{active_rep.get('error_code') or 'ROSTER_KEY_NOT_ACTIVE'}")
                                continue
                            resolved_pub = publisher_roster.resolve_pubkey_for_key_id(roster_obj, key_id, str(roster_path))
                            if not bool(resolved_pub.get("ok")):
                                prep_errors.append(f"{key_id}:{resolved_pub.get('error_code') or 'ROSTER_KEY_UNKNOWN'}")
                                continue
                            pub_path = Path(str(resolved_pub.get("path") or "")).resolve()
                            if (not roster_path_explicit) and (not _path_within(pub_path, persist)):
                                prep_errors.append(f"{key_id}:ROSTER_KEY_PATH_FORBIDDEN")
                                continue
                            priv_path = _resolve_signer_priv_path(persist, key_id)
                            if not _path_within(priv_path, persist):
                                prep_errors.append(f"{key_id}:PUBLISHER_KEY_PATH_FORBIDDEN")
                                continue
                            if not priv_path.exists() or not priv_path.is_file():
                                prep_errors.append(f"{key_id}:PUBLISHER_PRIVKEY_MISSING")
                                continue
                            roster_fp_claimed = str(key_row.get("pub_fingerprint") or "").strip().lower()
                            roster_fp_actual = bundle_signing.pub_fingerprint_from_path(str(pub_path))
                            if roster_fp_claimed and roster_fp_actual and roster_fp_claimed != roster_fp_actual:
                                prep_errors.append(f"{key_id}:PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH")
                                continue
                            pub_rel = str(key_row.get("pub_path") or "").strip().replace("\\", "/")
                            if pub_rel:
                                pub_dst = (bundle_root / pub_rel).resolve()
                                if _path_within(pub_dst, bundle_root):
                                    _copy_file(pub_path, pub_dst)
                            multisig_signers.append(
                                {
                                    "key_id": key_id,
                                    "priv_path": str(priv_path),
                                    "pub_fingerprint": str(roster_fp_actual or roster_fp_claimed or ""),
                                }
                            )

                        if prep_errors:
                            multisig_error = "PUBLISHER_SIGNING_FAILED"
                            export_warnings.extend([f"publisher_multisig_error:{row}" for row in prep_errors])
                        elif len({str(x.get('key_id') or '') for x in multisig_signers}) < threshold:
                            multisig_error = "MULTISIG_THRESHOLD_NOT_MET"
                        else:
                            policy_schema = str(roster_policy.get("schema") or "ester.publisher.policy.v1")
                            publisher_policy = {
                                "schema": "ester.publisher.bundle_policy.v1",
                                "threshold": int(threshold),
                                "of": int(of_count),
                                "roster_body_sha256": str(roster_body_sha or publisher_roster.compute_body_sha256(roster_obj)),
                                "roster_id": str(roster_obj.get("roster_id") or ""),
                                "enforce_roster": True,
                                "policy_schema": policy_schema,
                            }
                            roster_snapshot = (keys_dir / "publisher_roster.json").resolve()
                            _copy_file(roster_path, roster_snapshot)
                            roster_snapshot_sha = _sha256_file(roster_snapshot)
                            (keys_dir / "publisher_roster.sha256").write_text(roster_snapshot_sha + "\n", encoding="utf-8")

        if multisig_error:
            if slot == "B" and (multi_signer_requested or roster_present):
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": multisig_error,
                            "detail": multisig_error,
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            if slot == "A":
                if multi_signer_requested and (not allow_legacy_single_sig):
                    export_warnings.append("publisher_multisig_policy:legacy_single_fallback_without_explicit_allow")
                export_warnings.append(f"publisher_multisig_fallback:{multisig_error}")
            publisher_sigs = []
            publisher_policy = {}
            multisig_signers = []
            use_multisig = False

    if publisher_policy:
        threshold_policy = int(max(1, _to_int(publisher_policy.get("threshold"), 1)))
        roster_anchor_required = bool(slot == "B" or threshold_policy > 1 or bool(ns.require_roster_log))
        anchor_roster_log = True
        if bool(ns.no_anchor_roster_log):
            if slot == "B":
                export_warnings.append("publisher_roster_anchor_forced_in_slot_b")
            else:
                anchor_roster_log = False
        if bool(ns.anchor_roster_log):
            anchor_roster_log = True
        roster_log_required = bool(roster_anchor_required)
        publisher_policy["roster_log_required"] = bool(roster_log_required)

        if anchor_roster_log:
            source_head = (persist / "keys" / "publisher_roster_log_head.json").resolve()
            source_log = (persist / "keys" / "publisher_roster_log.jsonl").resolve()
            if (not _path_within(source_head, persist)) or (not _path_within(source_log, persist)):
                print(json.dumps({"ok": False, "error": "roster_log_path_forbidden"}, ensure_ascii=True, indent=2))
                return 2

            if not str(roster_root_pubkey or ""):
                if roster_log_required:
                    print(json.dumps({"ok": False, "error": "roster_root_pubkey_required"}, ensure_ascii=True, indent=2))
                    return 2
                export_warnings.append("publisher_roster_anchor_omitted:ROSTER_ROOT_PUBKEY_REQUIRED")
                publisher_policy["roster_log_required"] = False
            elif (not source_log.exists()) or (not source_log.is_file()):
                if roster_log_required:
                    print(json.dumps({"ok": False, "error": "roster_log_missing"}, ensure_ascii=True, indent=2))
                    return 2
                export_warnings.append("publisher_roster_anchor_omitted:ROSTER_LOG_REQUIRED")
                publisher_policy["roster_log_required"] = False
            else:
                verify_log = publisher_transparency_log.verify_log_chain(
                    str(source_log),
                    str(roster_root_pubkey),
                    require_strict_append=True,
                    require_publications=False,
                )
                if not bool(verify_log.get("ok")):
                    if roster_log_required:
                        print(
                            json.dumps(
                                {
                                    "ok": False,
                                    "error": "roster_log_invalid",
                                    "error_code": str(verify_log.get("error_code") or "LOG_CHAIN_BROKEN"),
                                    "detail": str(verify_log.get("error") or "roster_log_invalid"),
                                },
                                ensure_ascii=True,
                                indent=2,
                            )
                        )
                        return 2
                    export_warnings.append(f"publisher_roster_anchor_omitted:{verify_log.get('error_code') or 'ROSTER_LOG_INVALID'}")
                    publisher_policy["roster_log_required"] = False
                else:
                    roster_anchor_log_rows = [dict(x) for x in list(verify_log.get("entries") or []) if isinstance(x, dict)]
                    head_obj = _read_json(source_head) if source_head.exists() and source_head.is_file() else {}
                    head_hash = str(head_obj.get("last_entry_hash") or verify_log.get("last_entry_hash") or "").strip().lower()

                    anchor_hash = str(roster_entry_override or "").strip().lower()
                    if not anchor_hash:
                        anchor_hash = str(head_hash or "").strip().lower()
                    if not anchor_hash:
                        anchor_hash = str(verify_log.get("last_entry_hash") or "").strip().lower()
                    if not _is_sha256(anchor_hash):
                        if roster_log_required:
                            print(json.dumps({"ok": False, "error": "roster_entry_hash_invalid"}, ensure_ascii=True, indent=2))
                            return 2
                        export_warnings.append("publisher_roster_anchor_omitted:ROSTER_ENTRY_HASH_INVALID")
                        publisher_policy["roster_log_required"] = False
                    else:
                        anchor_entry, anchor_idx = _find_log_entry(roster_anchor_log_rows, anchor_hash)
                        if not anchor_entry:
                            if roster_log_required:
                                print(json.dumps({"ok": False, "error": "roster_log_entry_not_found", "entry_hash": anchor_hash}, ensure_ascii=True, indent=2))
                                return 2
                            export_warnings.append("publisher_roster_anchor_omitted:ROSTER_LOG_ENTRY_NOT_FOUND")
                            publisher_policy["roster_log_required"] = False
                        else:
                            anchor_body = str(anchor_entry.get("body_sha256") or "").strip().lower()
                            policy_body = str(publisher_policy.get("roster_body_sha256") or "").strip().lower()
                            if anchor_body != policy_body:
                                if roster_log_required:
                                    print(
                                        json.dumps(
                                            {
                                                "ok": False,
                                                "error": "roster_anchor_body_mismatch",
                                                "anchor_body_sha256": anchor_body,
                                                "policy_body_sha256": policy_body,
                                            },
                                            ensure_ascii=True,
                                            indent=2,
                                        )
                                    )
                                    return 2
                                export_warnings.append("publisher_roster_anchor_omitted:ROSTER_ANCHOR_BODY_MISMATCH")
                                publisher_policy["roster_log_required"] = False
                            else:
                                anchor_roster_id = str(anchor_entry.get("roster_id") or "")
                                policy_roster_id = str(publisher_policy.get("roster_id") or "")
                                if policy_roster_id and anchor_roster_id and policy_roster_id != anchor_roster_id:
                                    if roster_log_required:
                                        print(
                                            json.dumps(
                                                {
                                                    "ok": False,
                                                    "error": "roster_anchor_roster_id_mismatch",
                                                    "anchor_roster_id": anchor_roster_id,
                                                    "policy_roster_id": policy_roster_id,
                                                },
                                                ensure_ascii=True,
                                                indent=2,
                                            )
                                        )
                                        return 2
                                    export_warnings.append("publisher_roster_anchor_omitted:ROSTER_ANCHOR_ROSTER_ID_MISMATCH")
                                    publisher_policy["roster_log_required"] = False
                                else:
                                    roster_anchor_entry_hash = str(anchor_hash)
                                    roster_anchor_index = int(anchor_idx)
                                    roster_log_head_hash = str(head_hash or verify_log.get("last_entry_hash") or "")
                                    publisher_policy["roster_entry_hash"] = roster_anchor_entry_hash
                                    publisher_policy["roster_log_head"] = str(roster_log_head_hash or "")
                                    publisher_policy["roster_log_required"] = bool(roster_log_required)
                                    roster_anchor = {
                                        "schema": "ester.publisher.roster_anchor.v1",
                                        "entry_hash": str(roster_anchor_entry_hash),
                                        "body_sha256": str(anchor_body),
                                        "roster_id": str(anchor_roster_id or policy_roster_id),
                                        "ts": int(_to_int(anchor_entry.get("ts"), 0)),
                                        "prev_hash": str(anchor_entry.get("prev_hash") or ""),
                                    }
        else:
            publisher_policy["roster_log_required"] = False

    include_roster_log_effective = bool(ns.include_roster_log) or bool(publisher_policy and publisher_policy.get("roster_log_required"))
    if include_roster_log_effective:
        if publisher_policy:
            source_head = (persist / "keys" / "publisher_roster_log_head.json").resolve()
            source_log = (persist / "keys" / "publisher_roster_log.jsonl").resolve()
            if (not _path_within(source_head, persist)) or (not _path_within(source_log, persist)):
                print(json.dumps({"ok": False, "error": "roster_log_path_forbidden"}, ensure_ascii=True, indent=2))
                return 2
            if (not source_head.exists()) or (not source_head.is_file()) or (not source_log.exists()) or (not source_log.is_file()):
                if bool(publisher_policy.get("roster_log_required")):
                    print(json.dumps({"ok": False, "error": "roster_log_missing"}, ensure_ascii=True, indent=2))
                    return 2
                export_warnings.append("publisher_roster_log_omitted:ROSTER_LOG_REQUIRED")
            else:
                head_obj = _read_json(source_head)
                last_n = max(1, int(ns.roster_log_last or 20))
                rows_log = roster_anchor_log_rows if roster_anchor_log_rows else _read_jsonl_rows(source_log)
                rows_tail = rows_log[-last_n:]

                if roster_anchor_entry_hash and (not any(str(dict(x).get("entry_hash") or "").strip().lower() == roster_anchor_entry_hash for x in rows_tail)):
                    if roster_anchor_index >= 0:
                        rows_tail = rows_log[roster_anchor_index:]
                    if not any(str(dict(x).get("entry_hash") or "").strip().lower() == roster_anchor_entry_hash for x in rows_tail):
                        if bool(publisher_policy.get("roster_log_required")):
                            print(json.dumps({"ok": False, "error": "roster_log_entry_not_found", "entry_hash": roster_anchor_entry_hash}, ensure_ascii=True, indent=2))
                            return 2
                        export_warnings.append("publisher_roster_log_omitted:ROSTER_LOG_ENTRY_NOT_FOUND")
                        rows_tail = []

                if rows_tail:
                    head_dst = (keys_dir / "publisher_roster_log_head.json").resolve()
                    log_dst = (keys_dir / "publisher_roster_log.jsonl").resolve()
                    _write_json(head_dst, head_obj if isinstance(head_obj, dict) else {})
                    log_dst.parent.mkdir(parents=True, exist_ok=True)
                    with log_dst.open("w", encoding="utf-8") as f:
                        for row in rows_tail:
                            f.write(json.dumps(dict(row), ensure_ascii=True, separators=(",", ":")) + "\n")

                    roster_log_included = True
                    roster_log_entries = len(rows_tail)
                    roster_log_head_hash = str((head_obj if isinstance(head_obj, dict) else {}).get("last_entry_hash") or roster_log_head_hash or "")
        else:
            export_warnings.append("publisher_roster_log_omitted:no_publisher_policy")

    legacy_pub_copy_required = bool(include_publisher_pubkey) and bool(signing_enabled) and (not bool(use_multisig))
    if legacy_pub_copy_required and (not _path_within(publisher_pub, persist)):
        print(json.dumps({"ok": False, "error": "publisher_pubkey_path_forbidden", "path": str(publisher_pub)}, ensure_ascii=True, indent=2))
        return 2
    if legacy_pub_copy_required:
        if publisher_pub.exists() and publisher_pub.is_file():
            _copy_file(publisher_pub, publisher_pub_bundle)
        else:
            print(json.dumps({"ok": False, "error": "publisher_pubkey_missing", "path": str(publisher_pub)}, ensure_ascii=True, indent=2))
            return 2

    tree_hash = _bundle_tree_hash(bundle_root)

    if signing_enabled and bool(use_multisig):
        sign_errors: List[str] = []
        for signer in multisig_signers:
            key_id = str(signer.get("key_id") or "")
            priv_path = str(signer.get("priv_path") or "")
            expected_fp = str(signer.get("pub_fingerprint") or "").strip().lower()
            try:
                sig = bundle_signing.sign_tree_hash(str(tree_hash or ""), priv_path, key_id=key_id)
            except Exception:
                sign_errors.append(f"{key_id}:PUBLISHER_SIGNING_FAILED")
                continue
            if str(sig.get("signed") or "").strip().lower() != str(tree_hash or "").strip().lower():
                sign_errors.append(f"{key_id}:PUBLISHER_SIG_SIGNED_MISMATCH")
                continue
            sig_fp = str(sig.get("pub_fingerprint") or "").strip().lower()
            if expected_fp and sig_fp and expected_fp != sig_fp:
                sign_errors.append(f"{key_id}:PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH")
                continue
            publisher_sigs.append(dict(sig))
        if publisher_sigs:
            publisher_fp = str((publisher_sigs[0] or {}).get("pub_fingerprint") or "")
        if sign_errors:
            multisig_error = "PUBLISHER_SIGNING_FAILED"
            export_warnings.extend([f"publisher_multisig_error:{row}" for row in sign_errors])
        elif len({str(x.get('key_id') or '') for x in publisher_sigs}) < max(1, multisig_threshold):
            multisig_error = "MULTISIG_THRESHOLD_NOT_MET"
        if multisig_error:
            if slot == "B":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": multisig_error,
                            "detail": multisig_error,
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            use_multisig = False
            publisher_sigs = []
            publisher_policy = {}
            export_warnings.append(f"publisher_multisig_fallback:{multisig_error}")

    if signing_enabled and (not use_multisig):
        sign_error = ""
        if (not _path_within(publisher_priv, persist)) or (not _path_within(publisher_pub, persist)):
            sign_error = "PUBLISHER_KEY_PATH_FORBIDDEN"
        elif not bundle_signing.is_available():
            sign_error = "ED25519_UNAVAILABLE"
        elif not publisher_priv.exists():
            sign_error = "PUBLISHER_PRIVKEY_MISSING"
        else:
            try:
                publisher_sig = bundle_signing.sign_tree_hash(
                    str(tree_hash or ""),
                    str(publisher_priv),
                    key_id=publisher_key_id,
                )
            except Exception as exc:
                sign_error = f"PUBLISHER_SIGNING_FAILED:{exc}"

        if sign_error:
            if slot == "B":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": sign_error.split(":", 1)[0],
                            "detail": sign_error,
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            export_warnings.append(f"publisher_sig_omitted:{sign_error}")
            publisher_sig = {}

    l4w_fp = _pub_fingerprint((keys_dir / "l4w_public.pem").resolve())
    ev_fp = _pub_fingerprint((keys_dir / "evidence_public.pem").resolve())
    if (not l4w_fp) and evidence_items:
        first_env = (bundle_root / "l4w" / "envelopes" / str(rows[-1].get("envelope_path") or "")).resolve() if rows else None
        if first_env and first_env.exists():
            l4w_fp = str((dict(_read_json(first_env).get("sig") or {})).get("pub_fingerprint") or "")
    if (not publisher_fp) and publisher_pub_bundle.exists() and publisher_pub_bundle.is_file():
        publisher_fp = _pub_fingerprint(publisher_pub_bundle)
    if (not publisher_fp) and publisher_pub.exists() and publisher_pub.is_file():
        publisher_fp = _pub_fingerprint(publisher_pub)

    _write_json(
        (keys_dir / "keys_fingerprint.json").resolve(),
        {
            "schema": "ester.keys.fingerprint.v1",
            "l4w_pub_fingerprint": str(l4w_fp or ""),
            "evidence_pub_fingerprint": str(ev_fp or l4w_fp or ""),
            "publisher_pub_fingerprint": str((dict(publisher_sig or {})).get("pub_fingerprint") or publisher_fp or ""),
        },
    )

    # keys_fingerprint.json is part of bundle_tree_sha256, so signatures must be bound after it is written.
    tree_hash = _bundle_tree_hash(bundle_root)
    if signing_enabled and publisher_sigs:
        resigned: List[Dict[str, Any]] = []
        resign_errors: List[str] = []
        for signer in multisig_signers:
            key_id = str(signer.get("key_id") or "")
            priv_path = str(signer.get("priv_path") or "")
            expected_fp = str(signer.get("pub_fingerprint") or "").strip().lower()
            try:
                sig = bundle_signing.sign_tree_hash(str(tree_hash or ""), priv_path, key_id=key_id)
            except Exception:
                resign_errors.append(f"{key_id}:PUBLISHER_SIGNING_FAILED")
                continue
            sig_fp = str(sig.get("pub_fingerprint") or "").strip().lower()
            if expected_fp and sig_fp and expected_fp != sig_fp:
                resign_errors.append(f"{key_id}:PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH")
                continue
            resigned.append(dict(sig))
        if resign_errors:
            if slot == "B":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": "PUBLISHER_SIGNING_FAILED",
                            "detail": ",".join(resign_errors),
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            export_warnings.append("publisher_multisig_fallback:resign_failed")
            publisher_sigs = []
            publisher_policy = {}
        elif len({str(x.get('key_id') or '') for x in resigned}) < max(1, multisig_threshold):
            if slot == "B":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": "MULTISIG_THRESHOLD_NOT_MET",
                            "detail": f"valid:{len(resigned)} threshold:{max(1, multisig_threshold)}",
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            export_warnings.append("publisher_multisig_fallback:threshold_not_met")
            publisher_sigs = []
            publisher_policy = {}
        else:
            publisher_sigs = resigned
            publisher_fp = str((publisher_sigs[0] or {}).get("pub_fingerprint") or publisher_fp)
    elif signing_enabled and publisher_sig:
        try:
            publisher_sig = bundle_signing.sign_tree_hash(str(tree_hash or ""), str(publisher_priv), key_id=publisher_key_id)
            publisher_fp = str(publisher_sig.get("pub_fingerprint") or publisher_fp)
        except Exception:
            if slot == "B":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": "PUBLISHER_SIGNING_FAILED",
                            "detail": "legacy_resign_failed",
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            export_warnings.append("publisher_sig_omitted:legacy_resign_failed")
            publisher_sig = {}

    last_hash = str(rows[-1].get("envelope_hash") or "").strip().lower() if rows else ""
    manifest: Dict[str, Any] = {
        "schema": "ester.l4w.bundle.v1",
        "created_ts": created_ts,
        "agent_id": aid,
        "profiles_supported": ["BASE", "HRO", "FULL"],
        "bundle_kind": "quarantine_clear",
        "roots": {
            "l4w_chains": "l4w/chains/quarantine_clear",
            "l4w_envelopes": "l4w/envelopes/quarantine_clear",
            "l4w_disclosures": "l4w/disclosures",
            "refs": "refs",
        },
        "includes": {
            "envelopes": True,
            "chain": True,
            "disclosures": bool(ns.include_disclosures),
            "evidence_files": bool(ns.include_evidence_files),
            "drift_events": bool(ns.include_cross_refs),
            "volition_journal": bool(ns.include_cross_refs),
            "publisher_sig": bool(signing_enabled and bool(publisher_sig)),
            "publisher_sigs": bool(publisher_sigs),
            "publisher_roster": bool(publisher_policy),
            "publisher_roster_log": bool(roster_log_included),
            "publisher_pubkey": bool(legacy_pub_copy_required),
        },
        "head": {
            "last_envelope_hash": last_hash,
            "records": len(rows),
        },
        "hashes": {
            "manifest_sha256": "",
            "bundle_tree_sha256": tree_hash,
        },
        "pubkeys": {
            "l4w_pub_fingerprint": str(l4w_fp or ""),
            "evidence_pub_fingerprint": str(ev_fp or l4w_fp or ""),
            "publisher_pub_fingerprint": str((dict(publisher_sig or {})).get("pub_fingerprint") or publisher_fp or ""),
        },
    }
    if publisher_sigs:
        manifest["publisher_sigs"] = list(publisher_sigs)
    if publisher_policy:
        manifest["publisher_policy"] = dict(publisher_policy)
    if roster_anchor:
        manifest["roster_anchor"] = dict(roster_anchor)
    if roster_log_included:
        manifest["publisher_roster_log"] = {
            "schema": "ester.publisher.roster_log_bundle_ref.v1",
            "head_path": "keys/publisher_roster_log_head.json",
            "log_path": "keys/publisher_roster_log.jsonl",
            "entries_count": int(roster_log_entries),
            "head_last_entry_hash": str(roster_log_head_hash or ""),
        }
    if publisher_sig:
        signed = str(publisher_sig.get("signed") or "").strip().lower()
        if signed != str(tree_hash or "").strip().lower():
            if slot == "B":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": "publisher_signing_failed",
                            "error_code": "PUBLISHER_SIG_SIGNED_MISMATCH",
                            "detail": f"signed:{signed} tree:{tree_hash}",
                            "slot": slot,
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                )
                return 2
            export_warnings.append("publisher_sig_omitted:PUBLISHER_SIG_SIGNED_MISMATCH")
        else:
            manifest["publisher_sig"] = publisher_sig

    manifest["hashes"]["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path = (bundle_root / "manifest.json").resolve()
    _write_json(manifest_path, manifest)
    (bundle_root / "hashes").mkdir(parents=True, exist_ok=True)
    (bundle_root / "hashes" / "manifest.sha256").write_text(str(manifest["hashes"]["manifest_sha256"]) + "\n", encoding="utf-8")
    _write_sha256s(bundle_root)

    zip_path = ""
    if bool(ns.zip):
        zip_name = f"bundle_{_safe_agent_file(aid)}_{created_ts}.zip"
        zip_target = (bundle_root.parent / zip_name).resolve()
        with zipfile.ZipFile(zip_target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(bundle_root.rglob("*")):
                if p.is_file():
                    arc = str(p.relative_to(bundle_root)).replace("\\", "/")
                    zf.write(p, arcname=arc)
        zip_path = str(zip_target)

    out = {
        "ok": True,
        "agent_id": aid,
        "profile": profile,
        "slot": slot,
        "bundle_dir": str(bundle_root),
        "bundle_zip": zip_path,
        "records": len(rows),
        "last_envelope_hash": last_hash,
        "includes": manifest.get("includes"),
        "publisher_sig_present": bool("publisher_sig" in manifest),
        "publisher_sigs_count": len([x for x in list(manifest.get("publisher_sigs") or []) if isinstance(x, dict)]),
        "publisher_multisig": bool(manifest.get("publisher_policy")),
        "publisher_roster_log_included": bool(roster_log_included),
        "publisher_roster_log_entries": int(roster_log_entries),
        "roster_anchor_present": bool(roster_anchor),
        "roster_entry_hash": str((dict(manifest.get("publisher_policy") or {})).get("roster_entry_hash") or ""),
        "publisher_pub_fingerprint": str((dict(manifest.get("pubkeys") or {})).get("publisher_pub_fingerprint") or ""),
        "warnings": list(export_warnings),
    }
    if bool(ns.json):
        print(json.dumps(out, ensure_ascii=True, indent=2))
    elif not bool(ns.quiet):
        print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
