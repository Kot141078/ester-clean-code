# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import bundle_signing, evidence_signing, l4w_witness, publisher_roster, publisher_transparency_log


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
    lines = [f"{rel}\t{sha}" for rel, sha in _bundle_tree_entries(bundle_root)]
    return _sha256_bytes("\n".join(lines).encode("utf-8"))


def _parse_sha256s(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        if "  " not in s:
            continue
        sha, rel = s.split("  ", 1)
        sha = sha.strip().lower()
        rel = rel.strip().replace("\\", "/")
        if _is_sha256(sha) and rel:
            out[rel] = sha
    return out


def _extract_zip_safely(src: Path, dst: Path) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(src, "r") as zf:
            for info in zf.infolist():
                name = str(info.filename or "").replace("\\", "/")
                if not name or name.startswith("/") or (".." in name.split("/")):
                    return {"ok": False, "error": "zip_path_forbidden", "entry": name}
                target = (dst / name).resolve()
                if not _path_within(target, dst):
                    return {"ok": False, "error": "zip_path_forbidden", "entry": name}
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src_file:
                    target.write_bytes(src_file.read())
    except Exception as exc:
        return {"ok": False, "error": f"zip_extract_error:{exc.__class__.__name__}"}
    return {"ok": True}


def _prepare_bundle_root(raw: str) -> Tuple[Path, Path | None, Dict[str, Any]]:
    path = Path(str(raw or "").strip()).resolve()
    if path.is_dir():
        return path, None, {"ok": True, "kind": "dir"}
    if path.is_file() and path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="ester_bundle_verify_")).resolve()
        rep = _extract_zip_safely(path, tmp)
        if not bool(rep.get("ok")):
            return tmp, tmp, rep
        return tmp, tmp, {"ok": True, "kind": "zip"}
    return path, None, {"ok": False, "error": "bundle_not_found"}


def _add_error(report: Dict[str, Any], code: str, where: str, detail: str) -> None:
    report.setdefault("errors", []).append({"code": str(code or "BUNDLE_VERIFY_ERROR"), "where": where, "detail": detail})


def _add_warning(report: Dict[str, Any], code: str, where: str, detail: str) -> None:
    report.setdefault("warnings", []).append({"code": str(code or "BUNDLE_VERIFY_WARN"), "where": where, "detail": detail})


def _extract_meta_ref(metadata: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    src = dict(metadata or {})
    for key in keys:
        raw = str(src.get(key) or "").strip().lower()
        if raw:
            return raw
    return ""


def _find_external_refs(events_rows: List[Dict[str, Any]], volition_rows: List[Dict[str, Any]], *, agent_id: str, event_id: str, envelope_hash: str, evidence_sha: str) -> bool:
    drift_ok = False
    vol_ok = False
    for row in events_rows:
        if str(row.get("type") or "") != "QUARANTINE_CLEAR":
            continue
        if str(row.get("agent_id") or "") != agent_id:
            continue
        if str(row.get("event_id") or "") != event_id:
            continue
        details = dict(row.get("details") or {})
        d_hash = str(details.get("l4w_envelope_hash") or "").strip().lower()
        d_sha = str(details.get("evidence_sha256") or "").strip().lower()
        if d_hash == envelope_hash and d_sha == evidence_sha:
            drift_ok = True
            break
    for row in volition_rows:
        step = str(row.get("step") or "").strip().lower()
        action_id = str(row.get("action_id") or "").strip().lower()
        metadata = dict(row.get("metadata") or {})
        meta_action = str(metadata.get("action_id") or "").strip().lower()
        if step != "drift.quarantine.clear" and action_id != "drift.quarantine.clear" and meta_action != "drift.quarantine.clear":
            continue
        v_agent = str(row.get("agent_id") or metadata.get("agent_id") or "").strip()
        if v_agent and v_agent != agent_id:
            continue
        v_event = str(metadata.get("quarantine_event_id") or row.get("event_id") or "").strip()
        if v_event and v_event != event_id:
            continue
        v_sha = _extract_meta_ref(metadata, ("evidence_sha256", "evidence_hash"))
        v_l4w = _extract_meta_ref(metadata, ("l4w_envelope_hash", "l4w_hash", "l4w_envelope_sha256"))
        if v_sha == evidence_sha and v_l4w == envelope_hash:
            vol_ok = True
            break
    return bool(drift_ok and vol_ok)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _collect_publisher_sigs(manifest: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    rows: List[Dict[str, Any]] = [dict(x) for x in list(manifest.get("publisher_sigs") or []) if isinstance(x, dict)]
    if rows:
        return rows, False
    legacy = dict(manifest.get("publisher_sig") or {})
    if legacy:
        return [legacy], True
    return [], False


def _find_log_entry(entries: List[Dict[str, Any]], entry_hash: str) -> Dict[str, Any]:
    target = str(entry_hash or "").strip().lower()
    if (not target) or (not _is_sha256(target)):
        return {}
    for row in entries:
        r = dict(row or {})
        if str(r.get("entry_hash") or "").strip().lower() == target:
            return r
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify L4W bundle (dir or zip)")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--profile", default="BASE")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--pubkey-publisher", default="")
    ap.add_argument("--publisher-roster", default="")
    ap.add_argument("--pubkey-roster-root", default="")
    ap.add_argument("--verify-roster-log", action="store_true")
    ap.add_argument("--roster-log", default="")
    ap.add_argument("--require-roster-entry-hash", action="store_true")
    ap.add_argument("--allow-missing-roster-entry-hash", action="store_true")
    ap.add_argument("--require-multisig", action="store_true")
    ap.add_argument("--allow-legacy-single-sig", action="store_true")
    ap.add_argument("--require-publisher-sig", action="store_true")
    ap.add_argument("--allow-missing-publisher-sig", action="store_true")
    ap.add_argument("--pubkey-l4w", default="")
    ap.add_argument("--pubkey-evidence", default="")
    ap.add_argument("--evidence-dir", default="")
    ap.add_argument("--events", default="")
    ap.add_argument("--volition", default="")
    ap.add_argument("--max-records", type=int, default=0)
    ap.add_argument("--allow-missing-evidence", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ns = ap.parse_args()

    profile = str(ns.profile or "BASE").strip().upper()
    report: Dict[str, Any] = {
        "ok": False,
        "profile": profile,
        "bundle": {"schema": "", "agent_id": "", "records": 0, "paths": {}},
        "checked": {"records": 0, "envelopes": 0, "disclosures": False, "evidence_files": False},
        "publisher": {
            "required": False,
            "present": False,
            "ok": False,
            "pub_fingerprint": "",
            "key_source": "missing",
            "error": "",
        },
        "publisher_roster": {
            "source": "missing",
            "ok": False,
            "roster_id": "",
            "body_sha256": "",
            "sig_ok": False,
            "error": "",
        },
        "publisher_roster_log": {
            "required": False,
            "ok": False,
            "path": "",
            "entries_count": 0,
            "last_entry_hash": "",
            "target_body_sha256": "",
            "target_found": False,
            "error": "",
        },
        "roster_anchor": {
            "required": False,
            "present": False,
            "ok": False,
            "entry_hash": "",
            "ts": 0,
            "body_sha256": "",
            "error": "",
        },
        "envelopes_roster_anchor": {
            "total": 0,
            "with_anchor": 0,
            "missing": 0,
            "mismatch": 0,
            "unknown_entry": 0,
        },
        "publisher_multisig": {
            "threshold": 1,
            "of": 1,
            "valid": 0,
            "required": False,
            "signers_ok": [],
        },
        "errors": [],
        "warnings": [],
        "head": {"last_envelope_hash": "", "ts": 0},
    }

    if profile not in {"BASE", "HRO", "FULL"}:
        _add_error(report, "PROFILE_INVALID", "input.profile", profile)

    root, cleanup, bundle_rep = _prepare_bundle_root(str(ns.bundle or ""))
    if not bool(bundle_rep.get("ok")):
        _add_error(report, "BUNDLE_NOT_FOUND", "input.bundle", str(bundle_rep.get("error") or "bundle_not_found"))

    try:
        manifest = _read_json((root / "manifest.json").resolve()) if bool(bundle_rep.get("ok")) else {}
        if str(manifest.get("schema") or "") != "ester.l4w.bundle.v1":
            _add_error(report, "BUNDLE_SCHEMA_INVALID", "manifest.schema", str(manifest.get("schema") or ""))
        agent_id = str(manifest.get("agent_id") or "")
        report["bundle"]["schema"] = str(manifest.get("schema") or "")
        report["bundle"]["agent_id"] = agent_id

        manifest_claimed_hash = str((dict(manifest.get("hashes") or {})).get("manifest_sha256") or "").strip().lower()
        manifest_actual_hash = _manifest_hash(manifest)
        if manifest_claimed_hash and manifest_claimed_hash != manifest_actual_hash:
            _add_error(report, "MANIFEST_HASH_MISMATCH", "manifest.hashes.manifest_sha256", f"claimed:{manifest_claimed_hash} actual:{manifest_actual_hash}")
        manifest_hash_file = (root / "hashes" / "manifest.sha256").resolve()
        if manifest_hash_file.exists():
            f_hash = str(manifest_hash_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()[0] if manifest_hash_file.read_text(encoding="utf-8", errors="replace").strip() else "").lower()
            if f_hash and f_hash != manifest_actual_hash:
                _add_error(report, "MANIFEST_HASH_MISMATCH", "hashes/manifest.sha256", f"file:{f_hash} actual:{manifest_actual_hash}")

        tree_claimed = str((dict(manifest.get("hashes") or {})).get("bundle_tree_sha256") or "").strip().lower()
        tree_actual = _bundle_tree_hash(root)
        if tree_claimed and tree_claimed != tree_actual:
            _add_error(report, "BUNDLE_TREE_HASH_MISMATCH", "manifest.hashes.bundle_tree_sha256", f"claimed:{tree_claimed} actual:{tree_actual}")

        sums_map = _parse_sha256s((root / "hashes" / "SHA256SUMS.txt").resolve())
        for rel, claimed_sha in sums_map.items():
            p = (root / rel).resolve()
            if (not p.exists()) or (not p.is_file()):
                _add_error(report, "BUNDLE_FILE_MISSING", f"hashes/SHA256SUMS:{rel}", "missing")
                continue
            actual_sha = _sha256_file(p)
            if actual_sha != claimed_sha:
                _add_error(report, "BUNDLE_FILE_HASH_MISMATCH", f"hashes/SHA256SUMS:{rel}", f"claimed:{claimed_sha} actual:{actual_sha}")

        require_publisher_sig = True
        if bool(ns.require_publisher_sig):
            require_publisher_sig = True
        allow_missing_publisher_sig = bool(ns.allow_missing_publisher_sig) and profile == "BASE"
        allow_legacy_single_sig = bool(ns.allow_legacy_single_sig) and profile == "BASE"

        publisher_sigs, legacy_single = _collect_publisher_sigs(manifest)
        publisher_policy = dict(manifest.get("publisher_policy") or {})
        policy_present = bool(publisher_policy)
        threshold = _to_int(publisher_policy.get("threshold"), 1 if not policy_present else 2)
        of_count = _to_int(publisher_policy.get("of"), max(1, threshold))
        enforce_roster = bool(publisher_policy.get("enforce_roster")) if policy_present else False
        policy_roster_log_required = bool(publisher_policy.get("roster_log_required")) if policy_present else False
        if not policy_present:
            threshold = 1
            of_count = 1
            enforce_roster = False
            policy_roster_log_required = False
        if bool(ns.require_multisig):
            threshold = max(2, threshold)
            of_count = max(of_count, threshold)
            enforce_roster = True
        expected_roster_body_sha = str(publisher_policy.get("roster_body_sha256") or "").strip().lower()
        expected_roster_entry_hash = str(publisher_policy.get("roster_entry_hash") or "").strip().lower()
        expected_roster_id = str(publisher_policy.get("roster_id") or "").strip()

        report["publisher"]["required"] = bool(require_publisher_sig or threshold > 0)
        report["publisher"]["present"] = bool(publisher_sigs)
        report["publisher_multisig"]["threshold"] = int(max(1, threshold))
        report["publisher_multisig"]["of"] = int(max(1, of_count))
        report["publisher_multisig"]["required"] = bool(max(1, threshold) > 1 or enforce_roster)

        roster_required = bool(enforce_roster)
        roster_source = "missing"
        roster_path = ""
        roster_obj: Dict[str, Any] = {}
        roster_body_sha = ""
        roster_sig_ok = False

        if str(ns.publisher_roster or "").strip():
            roster_source = "cli"
            roster_path = str(Path(str(ns.publisher_roster or "").strip()).resolve())
        else:
            bundle_roster = (root / "keys" / "publisher_roster.json").resolve()
            if bundle_roster.exists() and bundle_roster.is_file():
                roster_source = "bundle"
                roster_path = str(bundle_roster)

        report["publisher_roster"]["source"] = roster_source
        if roster_source == "bundle" and roster_path and (not _path_within(Path(roster_path), root)):
            _add_error(report, "ROSTER_REQUIRED", "bundle/keys/publisher_roster.json", "path_forbidden")
            roster_path = ""

        if roster_path:
            loaded_roster = publisher_roster.load_roster(roster_path)
            if not bool(loaded_roster.get("ok")):
                _add_error(
                    report,
                    str(loaded_roster.get("error_code") or "ROSTER_REQUIRED"),
                    "publisher_roster",
                    str(loaded_roster.get("error") or "roster_invalid"),
                )
            else:
                roster_obj = publisher_roster.normalize_roster(dict(loaded_roster.get("roster") or {}))
                report["publisher_roster"]["roster_id"] = str(roster_obj.get("roster_id") or "")
                roster_root_pubkey = str(ns.pubkey_roster_root or os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "").strip()
                if not roster_root_pubkey:
                    if roster_required:
                        _add_error(report, "ROSTER_ROOT_PUBKEY_REQUIRED", "publisher_roster.sig", "missing_root_pubkey")
                    else:
                        _add_warning(report, "ROSTER_ROOT_PUBKEY_REQUIRED", "publisher_roster.sig", "missing_root_pubkey")
                else:
                    verify_roster = publisher_roster.verify_roster_sig(roster_obj, str(Path(roster_root_pubkey).resolve()))
                    roster_body_sha = str(verify_roster.get("body_sha256") or publisher_roster.compute_body_sha256(roster_obj))
                    report["publisher_roster"]["body_sha256"] = roster_body_sha
                    if not bool(verify_roster.get("ok")):
                        code = str(verify_roster.get("error_code") or "ROSTER_SIG_INVALID")
                        if roster_required:
                            _add_error(report, code, "publisher_roster.sig", str(verify_roster.get("error") or "roster_sig_invalid"))
                        else:
                            _add_warning(report, code, "publisher_roster.sig", str(verify_roster.get("error") or "roster_sig_invalid"))
                    else:
                        roster_sig_ok = True
                        report["publisher_roster"]["ok"] = True
                        report["publisher_roster"]["sig_ok"] = True
        elif roster_required:
            _add_error(report, "ROSTER_REQUIRED", "publisher_roster", "missing")

        if expected_roster_body_sha and roster_body_sha and expected_roster_body_sha != roster_body_sha:
            _add_error(
                report,
                "ROSTER_DIGEST_MISMATCH",
                "manifest.publisher_policy.roster_body_sha256",
                f"claimed:{expected_roster_body_sha} actual:{roster_body_sha}",
            )
        if expected_roster_body_sha and (not roster_body_sha) and roster_required:
            _add_error(report, "ROSTER_DIGEST_MISMATCH", "manifest.publisher_policy.roster_body_sha256", "missing_roster_digest")

        allow_missing_roster_entry_hash = bool(ns.allow_missing_roster_entry_hash) and profile == "BASE"
        require_roster_entry_hash = bool(ns.require_roster_entry_hash)
        if profile in {"HRO", "FULL"} and policy_present and (enforce_roster or policy_roster_log_required or bool(expected_roster_entry_hash)):
            require_roster_entry_hash = True
        elif profile == "BASE" and policy_present and enforce_roster and (not allow_missing_roster_entry_hash):
            require_roster_entry_hash = True
        if policy_roster_log_required:
            require_roster_entry_hash = True
        if bool(ns.require_roster_entry_hash) or profile in {"HRO", "FULL"}:
            allow_missing_roster_entry_hash = False

        verify_roster_log_enabled = bool(ns.verify_roster_log)
        if profile in {"HRO", "FULL"} and policy_present and (enforce_roster or policy_roster_log_required or bool(expected_roster_entry_hash)):
            verify_roster_log_enabled = True
        if policy_roster_log_required:
            verify_roster_log_enabled = True
        if require_roster_entry_hash:
            verify_roster_log_enabled = True

        report["publisher_roster_log"]["required"] = bool(verify_roster_log_enabled and policy_present and (policy_roster_log_required or require_roster_entry_hash))
        report["roster_anchor"]["required"] = bool(policy_present and require_roster_entry_hash)

        roster_log_entries: List[Dict[str, Any]] = []
        roster_log_by_hash: Dict[str, Dict[str, Any]] = {}
        roster_log_ready = False

        if verify_roster_log_enabled and policy_present:
            roster_root_pubkey = str(ns.pubkey_roster_root or os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "").strip()
            if not roster_root_pubkey:
                _add_error(report, "ROSTER_LOG_REQUIRED", "publisher_roster_log", "missing_root_pubkey")
            else:
                log_path: Path | None = None
                if str(ns.roster_log or "").strip():
                    log_path = Path(str(ns.roster_log or "").strip()).resolve()
                else:
                    bundle_log = (root / "keys" / "publisher_roster_log.jsonl").resolve()
                    if _path_within(bundle_log, root) and bundle_log.exists() and bundle_log.is_file():
                        log_path = bundle_log
                report["publisher_roster_log"]["path"] = str(log_path) if isinstance(log_path, Path) else ""
                if log_path is None:
                    if bool(report["publisher_roster_log"]["required"]):
                        _add_error(report, "ROSTER_LOG_REQUIRED", "publisher_roster_log", "missing")
                    else:
                        _add_warning(report, "ROSTER_LOG_REQUIRED", "publisher_roster_log", "missing")
                elif (not log_path.exists()) or (not log_path.is_file()):
                    _add_error(report, "ROSTER_LOG_REQUIRED", "publisher_roster_log", str(log_path))
                else:
                    v_log = publisher_transparency_log.verify_log_chain(
                        str(log_path),
                        str(Path(roster_root_pubkey).resolve()),
                        require_strict_append=False,
                        require_publications=False,
                    )
                    report["publisher_roster_log"]["entries_count"] = int(v_log.get("entries_count") or 0)
                    report["publisher_roster_log"]["last_entry_hash"] = str(v_log.get("last_entry_hash") or "")
                    if not bool(v_log.get("ok")):
                        report["publisher_roster_log"]["error"] = str(v_log.get("error") or "roster_log_invalid")
                        _add_error(
                            report,
                            "ROSTER_LOG_INVALID",
                            "publisher_roster_log",
                            str(v_log.get("error") or "roster_log_invalid"),
                        )
                    else:
                        roster_log_entries = [dict(x) for x in list(v_log.get("entries") or []) if isinstance(x, dict)]
                        roster_log_by_hash = {
                            str(dict(x).get("entry_hash") or "").strip().lower(): dict(x)
                            for x in roster_log_entries
                            if _is_sha256(str(dict(x).get("entry_hash") or "").strip().lower())
                        }
                        roster_log_ready = True
                        report["publisher_roster_log"]["ok"] = True
                        report["publisher_roster_log"]["target_body_sha256"] = str(expected_roster_body_sha or roster_body_sha or "").strip().lower()

                        policy_anchor_hash = str(expected_roster_entry_hash or "").strip().lower()
                        report["roster_anchor"]["present"] = bool(policy_anchor_hash)
                        report["roster_anchor"]["entry_hash"] = policy_anchor_hash
                        if (not policy_anchor_hash) and require_roster_entry_hash:
                            if allow_missing_roster_entry_hash:
                                _add_warning(report, "ROSTER_ENTRY_HASH_REQUIRED", "manifest.publisher_policy.roster_entry_hash", "missing_but_allowed")
                            else:
                                report["roster_anchor"]["error"] = "roster_entry_hash_missing"
                                _add_error(report, "ROSTER_ENTRY_HASH_REQUIRED", "manifest.publisher_policy.roster_entry_hash", "missing")
                        elif (not policy_anchor_hash) and allow_missing_roster_entry_hash and policy_present and enforce_roster:
                            _add_warning(report, "ROSTER_ENTRY_HASH_REQUIRED", "manifest.publisher_policy.roster_entry_hash", "missing_but_allowed")
                        elif policy_anchor_hash:
                            anchor_entry = _find_log_entry(roster_log_entries, policy_anchor_hash)
                            if not anchor_entry:
                                report["roster_anchor"]["error"] = "roster_log_entry_not_found"
                                _add_error(report, "ROSTER_LOG_ENTRY_NOT_FOUND", "manifest.publisher_policy.roster_entry_hash", policy_anchor_hash)
                            else:
                                report["publisher_roster_log"]["target_found"] = True
                                anchor_body = str(anchor_entry.get("body_sha256") or "").strip().lower()
                                anchor_roster_id = str(anchor_entry.get("roster_id") or "")
                                anchor_ts = int(_to_int(anchor_entry.get("ts"), 0))
                                report["roster_anchor"]["body_sha256"] = anchor_body
                                report["roster_anchor"]["ts"] = anchor_ts

                                if expected_roster_body_sha and anchor_body != expected_roster_body_sha:
                                    report["roster_anchor"]["error"] = "roster_anchor_body_mismatch"
                                    _add_error(
                                        report,
                                        "ROSTER_ANCHOR_BODY_MISMATCH",
                                        "manifest.publisher_policy.roster_body_sha256",
                                        f"anchor:{anchor_body} policy:{expected_roster_body_sha}",
                                    )
                                if expected_roster_id and anchor_roster_id and expected_roster_id != anchor_roster_id:
                                    report["roster_anchor"]["error"] = "roster_anchor_roster_id_mismatch"
                                    _add_error(
                                        report,
                                        "ROSTER_ANCHOR_ROSTER_ID_MISMATCH",
                                        "manifest.publisher_policy.roster_id",
                                        f"anchor:{anchor_roster_id} policy:{expected_roster_id}",
                                    )

                                manifest_anchor = dict(manifest.get("roster_anchor") or {})
                                if require_roster_entry_hash and not manifest_anchor:
                                    report["roster_anchor"]["error"] = "roster_anchor_missing"
                                    _add_error(report, "ROSTER_ENTRY_HASH_REQUIRED", "manifest.roster_anchor", "missing")
                                if manifest_anchor:
                                    if str(manifest_anchor.get("entry_hash") or "").strip().lower() != policy_anchor_hash:
                                        report["roster_anchor"]["error"] = "roster_entry_hash_mismatch"
                                        _add_error(report, "ROSTER_LOG_INVALID", "manifest.roster_anchor.entry_hash", "policy_mismatch")
                                    if str(manifest_anchor.get("body_sha256") or "").strip().lower() != anchor_body:
                                        report["roster_anchor"]["error"] = "roster_anchor_body_mismatch"
                                        _add_error(report, "ROSTER_ANCHOR_BODY_MISMATCH", "manifest.roster_anchor.body_sha256", "entry_mismatch")
                                    if str(manifest_anchor.get("roster_id") or "").strip() != anchor_roster_id:
                                        report["roster_anchor"]["error"] = "roster_anchor_roster_id_mismatch"
                                        _add_error(report, "ROSTER_ANCHOR_ROSTER_ID_MISMATCH", "manifest.roster_anchor.roster_id", "entry_mismatch")
                                    if int(_to_int(manifest_anchor.get("ts"), 0)) != anchor_ts:
                                        report["roster_anchor"]["error"] = "roster_anchor_ts_mismatch"
                                        _add_error(report, "ROSTER_LOG_INVALID", "manifest.roster_anchor.ts", "entry_mismatch")
                                    if str(manifest_anchor.get("prev_hash") or "").strip().lower() != str(anchor_entry.get("prev_hash") or "").strip().lower():
                                        report["roster_anchor"]["error"] = "roster_anchor_prev_hash_mismatch"
                                        _add_error(report, "ROSTER_LOG_INVALID", "manifest.roster_anchor.prev_hash", "entry_mismatch")

                                manifest_created_ts = _to_int(manifest.get("created_ts"), 0)
                                if manifest_created_ts > 0 and anchor_ts > manifest_created_ts:
                                    report["roster_anchor"]["error"] = "roster_anchor_backdated"
                                    _add_error(
                                        report,
                                        "ROSTER_LOG_INVALID",
                                        "manifest.created_ts",
                                        f"anchor_ts:{anchor_ts} manifest_ts:{manifest_created_ts}",
                                    )
                                report["roster_anchor"]["ok"] = bool(not report["roster_anchor"]["error"])
                        if (not report["roster_anchor"]["error"]) and (
                            (not report["roster_anchor"]["required"]) or bool(report["roster_anchor"]["present"])
                        ):
                            report["roster_anchor"]["ok"] = True
        elif verify_roster_log_enabled:
            _add_warning(report, "ROSTER_LOG_SKIPPED_NO_POLICY", "publisher_roster_log", "publisher_policy_missing")

        if allow_missing_roster_entry_hash and policy_present and enforce_roster and (not expected_roster_entry_hash):
            _add_warning(report, "ROSTER_ENTRY_HASH_REQUIRED", "manifest.publisher_policy.roster_entry_hash", "missing_but_allowed")

        if (not publisher_sigs) and report["publisher"]["required"]:
            report["publisher"]["error"] = "publisher_sig_missing"
            if allow_missing_publisher_sig and (not roster_required) and threshold <= 1:
                _add_warning(report, "PUBLISHER_SIG_REQUIRED", "manifest.publisher_sig", "missing_but_allowed")
            else:
                _add_error(report, "PUBLISHER_SIG_REQUIRED", "manifest.publisher_sig", "missing")

        signer_reports: List[Dict[str, Any]] = []
        valid_distinct: Dict[str, bool] = {}
        pubkey_fingerprint = ""
        pubkey_source = "missing"
        manifest_created_ts = _to_int(manifest.get("created_ts"), 0)
        for idx_sig, sig in enumerate(publisher_sigs):
            key_id = str(sig.get("key_id") or f"sig_{idx_sig}")
            where = f"manifest.publisher_sigs[{idx_sig}]"
            if legacy_single:
                where = "manifest.publisher_sig"
            signer_row = {"key_id": key_id, "ok": False, "code": ""}
            signer_key_path = ""
            signer_roster_key: Dict[str, Any] = {}

            if roster_obj:
                resolved = publisher_roster.resolve_pubkey_for_key_id(roster_obj, key_id, roster_path)
                if not bool(resolved.get("ok")):
                    code = str(resolved.get("error_code") or "ROSTER_KEY_UNKNOWN")
                    signer_row["code"] = code
                    _add_error(report, code, where, str(resolved.get("error") or "roster_key_unknown"))
                    signer_reports.append(signer_row)
                    continue
                signer_key_path = str(resolved.get("path") or "")
                signer_roster_key = dict(resolved.get("key") or {})
                active = publisher_roster.is_key_active_at(signer_roster_key, manifest_created_ts)
                if not bool(active.get("ok")):
                    code = str(active.get("error_code") or "ROSTER_KEY_NOT_ACTIVE")
                    signer_row["code"] = code
                    _add_error(report, code, where, str(active.get("error") or "roster_key_not_active"))
                    signer_reports.append(signer_row)
                    continue
                pubkey_source = roster_source
            else:
                if str(ns.pubkey_publisher or "").strip():
                    signer_key_path = str(Path(str(ns.pubkey_publisher or "").strip()).resolve())
                    pubkey_source = "cli"
                else:
                    bundle_pub = (root / "keys" / "publisher_public.pem").resolve()
                    if bundle_pub.exists() and bundle_pub.is_file():
                        signer_key_path = str(bundle_pub)
                        pubkey_source = "bundle"
            if not signer_key_path:
                signer_row["code"] = "PUBLISHER_PUBKEY_MISSING"
                _add_error(report, "PUBLISHER_PUBKEY_MISSING", where, "missing")
                signer_reports.append(signer_row)
                continue

            sig_check = bundle_signing.verify_tree_hash_sig(tree_claimed, sig, signer_key_path)
            if not bool(sig_check.get("ok")):
                code = str(sig_check.get("error_code") or "PUBLISHER_SIG_INVALID")
                signer_row["code"] = code
                _add_error(report, code, where, str(sig_check.get("error") or "publisher_sig_invalid"))
                signer_reports.append(signer_row)
                continue

            claimed_roster_fp = str(signer_roster_key.get("pub_fingerprint") or "").strip().lower()
            actual_fp = str(sig_check.get("pub_fingerprint") or "").strip().lower()
            if claimed_roster_fp and actual_fp and claimed_roster_fp != actual_fp:
                signer_row["code"] = "PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH"
                _add_error(report, "PUBLISHER_PUBKEY_FINGERPRINT_MISMATCH", where, "roster_pub_fingerprint_mismatch")
                signer_reports.append(signer_row)
                continue

            signer_row["ok"] = True
            signer_reports.append(signer_row)
            if actual_fp and (not pubkey_fingerprint):
                pubkey_fingerprint = actual_fp
            distinct_id = key_id or actual_fp or f"sig_{idx_sig}"
            if not valid_distinct.get(distinct_id):
                valid_distinct[distinct_id] = True

        valid_count = len(valid_distinct)
        report["publisher"]["key_source"] = pubkey_source
        report["publisher"]["pub_fingerprint"] = pubkey_fingerprint
        report["publisher"]["ok"] = bool(valid_count > 0 and not report["publisher"].get("error"))
        report["publisher_multisig"]["valid"] = int(valid_count)
        report["publisher_multisig"]["signers_ok"] = signer_reports

        if legacy_single and (max(1, threshold) > 1 or roster_required):
            if allow_legacy_single_sig and (not roster_required):
                _add_warning(report, "LEGACY_SINGLE_SIG_NOT_ALLOWED", "manifest.publisher_sig", "allowed_in_base")
            else:
                _add_error(report, "LEGACY_SINGLE_SIG_NOT_ALLOWED", "manifest.publisher_sig", "policy_requires_multisig")
        if max(1, threshold) > 1 and valid_count < max(1, threshold):
            _add_error(
                report,
                "MULTISIG_THRESHOLD_NOT_MET",
                "manifest.publisher_sigs",
                f"valid:{valid_count} threshold:{max(1, threshold)}",
            )
        if roster_required and (not roster_sig_ok):
            report["publisher_roster"]["error"] = "roster_sig_invalid"

        chain_root = (root / "l4w" / "chains" / "quarantine_clear").resolve()
        chain_path = (chain_root / f"{_safe_agent_file(agent_id)}.jsonl").resolve()
        if (not chain_path.exists()) or (not chain_path.is_file()):
            fallback = sorted(chain_root.glob("*.jsonl"))
            if len(fallback) == 1:
                chain_path = fallback[0].resolve()
            else:
                _add_error(report, "CHAIN_FILE_MISSING", "chain", str(chain_path))

        rows: List[Dict[str, Any]] = []
        if chain_path.exists() and chain_path.is_file():
            with chain_path.open("r", encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                    except Exception:
                        _add_error(report, "CHAIN_RECORD_INVALID", f"chain:{line_no}", "json_invalid")
                        continue
                    if isinstance(obj, dict):
                        rows.append(dict(obj))
                    else:
                        _add_error(report, "CHAIN_RECORD_INVALID", f"chain:{line_no}", "row_not_object")
        if int(ns.max_records or 0) > 0:
            rows = rows[-max(1, int(ns.max_records or 0)) :]

        report["bundle"]["records"] = len(rows)
        if rows:
            report["head"]["last_envelope_hash"] = str(rows[-1].get("envelope_hash") or "")
            report["head"]["ts"] = int(rows[-1].get("ts") or 0)

        evidence_index = _read_json((root / "refs" / "evidence_index.json").resolve())
        if str(evidence_index.get("schema") or "") != "ester.l4w.evidence_index.v1":
            _add_error(report, "EVIDENCE_INDEX_INVALID", "refs/evidence_index.json", "schema_invalid")
        idx_items = [dict(x) for x in list(evidence_index.get("items") or []) if isinstance(x, dict)]
        by_env_hash: Dict[str, Dict[str, Any]] = {}
        for item in idx_items:
            h = str(item.get("envelope_hash") or "").strip().lower()
            if h:
                by_env_hash[h] = item

        l4w_pub = Path(str(ns.pubkey_l4w or "").strip()).resolve() if str(ns.pubkey_l4w or "").strip() else (root / "keys" / "l4w_public.pem").resolve()
        if (not l4w_pub.exists()) and (not str(ns.pubkey_l4w or "").strip()):
            alt = (root / "keys" / "evidence_public.pem").resolve()
            if alt.exists():
                l4w_pub = alt
        evidence_pub = Path(str(ns.pubkey_evidence or "").strip()).resolve() if str(ns.pubkey_evidence or "").strip() else (root / "keys" / "evidence_public.pem").resolve()
        if (not evidence_pub.exists()) and (not str(ns.pubkey_evidence or "").strip()):
            if l4w_pub.exists():
                evidence_pub = l4w_pub

        seen_hash: Dict[str, int] = {}
        first = True
        prev_hash = ""
        has_evidence_files = False
        strict = bool(ns.strict) or profile in {"HRO", "FULL"}
        disclosures_in_bundle = (root / "l4w" / "disclosures").exists()

        for idx, row in enumerate(rows):
            where = f"chain[{idx}]"
            rec_hash = str(row.get("envelope_hash") or "").strip().lower()
            rec_prev = str(row.get("prev_hash") or "").strip().lower()
            rec_path = str(row.get("envelope_path") or "").strip().replace("\\", "/")
            rec_sha = str(row.get("envelope_sha256") or "").strip().lower()
            rec_ts = int(row.get("ts") or 0)
            report["checked"]["records"] = int(report["checked"]["records"]) + 1

            if first:
                if rec_prev:
                    _add_warning(report, "CHAIN_TRUNCATED", where, f"anchor_prev_hash:{rec_prev}")
                first = False
            else:
                if rec_prev != prev_hash:
                    _add_error(report, "L4W_CHAIN_BROKEN", f"{where}.prev_hash", f"expected:{prev_hash} got:{rec_prev}")
            prev_hash = rec_hash

            if profile == "FULL":
                old = seen_hash.get(rec_hash)
                if old is not None:
                    _add_error(report, "L4W_DUPLICATE_ENVELOPE_HASH", where, f"duplicate_of:{old}")
            elif profile == "HRO":
                old = seen_hash.get(rec_hash)
                if old is not None:
                    _add_warning(report, "L4W_DUPLICATE_ENVELOPE_HASH", where, f"duplicate_of:{old}")
            seen_hash[rec_hash] = idx

            env_file = (root / "l4w" / "envelopes" / rec_path).resolve()
            if (not _path_within(env_file, root)) or (not env_file.exists()) or (not env_file.is_file()):
                _add_error(report, "L4W_FILE_NOT_FOUND", f"{where}.envelope_path", rec_path)
                continue
            report["checked"]["envelopes"] = int(report["checked"]["envelopes"]) + 1

            env_sha_actual = _sha256_file(env_file)
            if rec_sha and rec_sha != env_sha_actual:
                _add_error(report, "L4W_HASH_MISMATCH", f"{where}.envelope_sha256", f"record:{rec_sha} actual:{env_sha_actual}")
            rel_env = str(env_file.relative_to(root)).replace("\\", "/")
            if rel_env in sums_map and sums_map[rel_env] != env_sha_actual:
                _add_error(report, "BUNDLE_FILE_HASH_MISMATCH", f"SHA256SUMS:{rel_env}", "envelope_hash_mismatch")

            env_obj = _read_json(env_file)
            if not env_obj:
                _add_error(report, "L4W_SCHEMA_INVALID", where, "envelope_json_invalid")
                continue
            env_chain = dict(env_obj.get("chain") or {})
            env_hash = str(env_chain.get("envelope_hash") or "").strip().lower()
            calc_hash = l4w_witness.compute_envelope_hash(env_obj)
            if env_hash != calc_hash:
                _add_error(report, "L4W_HASH_MISMATCH", f"{where}.chain.envelope_hash", f"chain:{env_hash} calc:{calc_hash}")
            if rec_hash != calc_hash:
                _add_error(report, "L4W_HASH_MISMATCH", f"{where}.record.envelope_hash", f"record:{rec_hash} calc:{calc_hash}")

            report["envelopes_roster_anchor"]["total"] = int(report["envelopes_roster_anchor"]["total"]) + 1
            env_roster_anchor = dict(env_obj.get("roster_anchor") or {})
            has_env_anchor = bool(env_roster_anchor)
            if has_env_anchor:
                report["envelopes_roster_anchor"]["with_anchor"] = int(report["envelopes_roster_anchor"]["with_anchor"]) + 1
            else:
                report["envelopes_roster_anchor"]["missing"] = int(report["envelopes_roster_anchor"]["missing"]) + 1
                if profile == "FULL" and policy_present and verify_roster_log_enabled:
                    _add_error(report, "ROSTER_ENTRY_HASH_REQUIRED", f"{where}.roster_anchor", "missing")
                elif profile == "HRO" and policy_present and verify_roster_log_enabled:
                    _add_warning(report, "ROSTER_ENTRY_HASH_REQUIRED", f"{where}.roster_anchor", "missing")

            if has_env_anchor and policy_present and verify_roster_log_enabled:
                env_anchor_hash = str(env_roster_anchor.get("entry_hash") or "").strip().lower()
                env_anchor_body = str(env_roster_anchor.get("body_sha256") or "").strip().lower()
                anchor_issue_level = "error"
                if profile == "BASE" and (not strict):
                    anchor_issue_level = "warning"
                if (not roster_log_ready) or (not env_anchor_hash) or (not _is_sha256(env_anchor_hash)):
                    report["envelopes_roster_anchor"]["unknown_entry"] = int(report["envelopes_roster_anchor"]["unknown_entry"]) + 1
                    if anchor_issue_level == "error":
                        _add_error(report, "ROSTER_LOG_ENTRY_NOT_FOUND", f"{where}.roster_anchor.entry_hash", env_anchor_hash or "missing")
                    else:
                        _add_warning(report, "ROSTER_LOG_ENTRY_NOT_FOUND", f"{where}.roster_anchor.entry_hash", env_anchor_hash or "missing")
                else:
                    anchor_entry = roster_log_by_hash.get(env_anchor_hash) or {}
                    if not anchor_entry:
                        report["envelopes_roster_anchor"]["unknown_entry"] = int(report["envelopes_roster_anchor"]["unknown_entry"]) + 1
                        if anchor_issue_level == "error":
                            _add_error(report, "ROSTER_LOG_ENTRY_NOT_FOUND", f"{where}.roster_anchor.entry_hash", env_anchor_hash)
                        else:
                            _add_warning(report, "ROSTER_LOG_ENTRY_NOT_FOUND", f"{where}.roster_anchor.entry_hash", env_anchor_hash)
                    else:
                        anchor_body = str(anchor_entry.get("body_sha256") or "").strip().lower()
                        if env_anchor_body != anchor_body:
                            report["envelopes_roster_anchor"]["mismatch"] = int(report["envelopes_roster_anchor"]["mismatch"]) + 1
                            if anchor_issue_level == "error":
                                _add_error(
                                    report,
                                    "ROSTER_ANCHOR_BODY_MISMATCH",
                                    f"{where}.roster_anchor.body_sha256",
                                    f"envelope:{env_anchor_body} log:{anchor_body}",
                                )
                            else:
                                _add_warning(
                                    report,
                                    "ROSTER_ANCHOR_BODY_MISMATCH",
                                    f"{where}.roster_anchor.body_sha256",
                                    f"envelope:{env_anchor_body} log:{anchor_body}",
                                )

            if not l4w_pub.exists():
                _add_error(report, "L4W_PUBKEY_MISSING", "keys", str(l4w_pub))
            else:
                v = l4w_witness.verify_envelope(env_obj, pub_path=str(l4w_pub))
                if not bool(v.get("ok")):
                    code = str(v.get("error_code") or "L4W_SIG_INVALID")
                    if str(v.get("error") or "") == "l4w_pub_fingerprint_mismatch":
                        code = "L4W_PUBKEY_FINGERPRINT_MISMATCH"
                    _add_error(report, code, where, str(v.get("error") or "sig_invalid"))

            subj = dict(env_obj.get("subject") or {})
            if str(subj.get("agent_id") or "") != agent_id:
                _add_error(report, "L4W_SUBJECT_MISMATCH", f"{where}.subject.agent_id", str(subj.get("agent_id") or ""))

            eref = dict(env_obj.get("evidence_ref") or {})
            eref_sha = str(eref.get("sha256") or "").strip().lower()
            eref_path = str(eref.get("path") or "").strip().replace("\\", "/")
            eref_payload = str(eref.get("evidence_payload_hash") or "").strip().lower()
            idx_item = by_env_hash.get(calc_hash) or {}
            if not idx_item:
                _add_error(report, "EVIDENCE_REF_MISSING", where, calc_hash)
                continue
            idx_evidence = dict(idx_item.get("evidence") or {})
            if str(idx_evidence.get("sha256") or "").strip().lower() != eref_sha:
                _add_error(report, "EVIDENCE_REF_MISMATCH", f"{where}.evidence_ref.sha256", "index_mismatch")
            if str(idx_evidence.get("path") or "").strip().replace("\\", "/") != eref_path:
                _add_error(report, "EVIDENCE_REF_MISMATCH", f"{where}.evidence_ref.path", "index_mismatch")

            event_id = str(idx_item.get("quarantine_event_id") or str(subj.get("quarantine_event_id") or "")).strip()
            has_bundle_file = bool(idx_item.get("has_evidence_file_in_bundle"))
            if has_bundle_file:
                has_evidence_files = True
            ev_packet_path = None
            if has_bundle_file:
                bundle_path = str(idx_item.get("bundle_path") or "").strip()
                if not bundle_path:
                    bundle_path = f"refs/evidence_files/{eref_path}"
                candidate = (root / bundle_path).resolve()
                if _path_within(candidate, root):
                    ev_packet_path = candidate
            elif str(ns.evidence_dir or "").strip():
                candidate = (Path(str(ns.evidence_dir or "").strip()).resolve() / eref_path).resolve()
                ev_packet_path = candidate

            if profile in {"HRO", "FULL"}:
                if ev_packet_path is None or (not ev_packet_path.exists()) or (not ev_packet_path.is_file()):
                    if not bool(ns.allow_missing_evidence):
                        _add_error(report, "EVIDENCE_FILES_MISSING_FOR_HRO", where, eref_path)
                    else:
                        _add_warning(report, "EVIDENCE_FILES_MISSING_FOR_HRO", where, eref_path)
                else:
                    report["checked"]["evidence_files"] = True
                    ev_actual_sha = _sha256_file(ev_packet_path).lower()
                    if ev_actual_sha != eref_sha:
                        _add_error(report, "EVIDENCE_HASH_MISMATCH", where, f"ref:{eref_sha} actual:{ev_actual_sha}")
                    ev_obj = _read_json(ev_packet_path)
                    if not ev_obj:
                        _add_error(report, "EVIDENCE_SCHEMA_INVALID", where, "evidence_json_invalid")
                    else:
                        if evidence_signing is None or (hasattr(evidence_signing, "is_available") and not evidence_signing.is_available()):
                            _add_error(report, "ED25519_UNAVAILABLE", where, "evidence_signing_unavailable")
                        else:
                            ev_verify = evidence_signing.verify_packet(ev_obj, pub_path=str(evidence_pub) if evidence_pub.exists() else "")
                            if not bool(ev_verify.get("ok")):
                                _add_error(report, str(ev_verify.get("error_code") or "EVIDENCE_SIG_INVALID"), where, str(ev_verify.get("error") or "evidence_sig_invalid"))
                            if eref_payload:
                                payload = str(ev_verify.get("payload_hash") or (dict(ev_obj.get("sig") or {})).get("payload_hash") or "").strip().lower()
                                if payload and payload != eref_payload:
                                    _add_error(report, "EVIDENCE_PAYLOAD_HASH_MISMATCH", where, f"ref:{eref_payload} actual:{payload}")

                if bool(manifest.get("includes", {}).get("disclosures")) or disclosures_in_bundle:
                    dis_path = (root / "l4w" / "disclosures" / f"{calc_hash}.json").resolve()
                    if dis_path.exists() and dis_path.is_file():
                        report["checked"]["disclosures"] = True
                        dis_obj = _read_json(dis_path)
                        dis_verify = l4w_witness.verify_disclosure(env_obj, dis_obj)
                        if not bool(dis_verify.get("ok")):
                            _add_error(report, str(dis_verify.get("error_code") or "L4W_SCHEMA_INVALID"), where, str(dis_verify.get("error") or "disclosure_invalid"))
                    elif bool(manifest.get("includes", {}).get("disclosures")):
                        _add_error(report, "L4W_DISCLOSURE_MISSING", where, calc_hash)

            if profile == "FULL":
                cross_refs_path = (root / "refs" / "cross_refs.json").resolve()
                has_cross_refs = cross_refs_path.exists() and cross_refs_path.is_file()
                has_external_refs = bool(str(ns.events or "").strip() and str(ns.volition or "").strip())
                if (not has_cross_refs) and (not has_external_refs):
                    if strict and (not bool(ns.allow_missing_evidence)):
                        _add_error(report, "FULL_REFS_MISSING", where, "cross_refs_missing")
                    else:
                        _add_warning(report, "FULL_REFS_MISSING", where, "cross_refs_missing")
                elif has_cross_refs:
                    cross = _read_json(cross_refs_path)
                    if str(cross.get("schema") or "") != "ester.l4w.cross_refs.v1":
                        _add_error(report, "FULL_REFS_INVALID", where, "cross_refs_schema_invalid")
                    rows_ref = [dict(x) for x in list(cross.get("items") or []) if isinstance(x, dict)]
                    hit = None
                    for ref in rows_ref:
                        if str(ref.get("quarantine_event_id") or "") == event_id and str(ref.get("envelope_hash") or "").lower() == calc_hash:
                            hit = ref
                            break
                    if not isinstance(hit, dict):
                        _add_error(report, "FULL_REFS_MISSING", where, f"event:{event_id}")
                    else:
                        drift_ok = bool(dict(hit.get("drift_event") or {}).get("found"))
                        vol_ok = bool(dict(hit.get("volition") or {}).get("found"))
                        if not drift_ok or not vol_ok:
                            _add_error(report, "FULL_REFS_MISSING", where, f"drift:{drift_ok} volition:{vol_ok}")
                else:
                    events_rows: List[Dict[str, Any]] = []
                    vol_rows: List[Dict[str, Any]] = []
                    events_path = Path(str(ns.events or "").strip()).resolve()
                    vol_path = Path(str(ns.volition or "").strip()).resolve()
                    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
                        s = line.strip()
                        if not s:
                            continue
                        try:
                            obj = json.loads(s)
                        except Exception:
                            continue
                        if isinstance(obj, dict):
                            events_rows.append(dict(obj))
                    for line in vol_path.read_text(encoding="utf-8", errors="replace").splitlines():
                        s = line.strip()
                        if not s:
                            continue
                        try:
                            obj = json.loads(s)
                        except Exception:
                            continue
                        if isinstance(obj, dict):
                            vol_rows.append(dict(obj))
                    if not _find_external_refs(events_rows, vol_rows, agent_id=agent_id, event_id=event_id, envelope_hash=calc_hash, evidence_sha=eref_sha):
                        _add_error(report, "FULL_REFS_MISSING", where, "external_refs_mismatch")

            if idx + 1 == len(rows):
                report["head"]["last_envelope_hash"] = calc_hash
                report["head"]["ts"] = rec_ts

        report["bundle"]["paths"] = {
            "root": str(root),
            "manifest": str((root / "manifest.json").resolve()),
            "chain": str(chain_path),
        }
        report["ok"] = bool(not report["errors"])
    finally:
        if cleanup is not None:
            shutil.rmtree(cleanup, ignore_errors=True)

    rc = 0
    if report["errors"]:
        rc = 2
    elif report["warnings"] and profile == "BASE":
        rc = 3

    if bool(ns.json):
        print(json.dumps(report, ensure_ascii=True, indent=2))
    elif bool(ns.quiet):
        print("PASS" if rc in {0, 3} else "FAIL")
    else:
        print("PASS" if rc in {0, 3} else "FAIL")
        if rc != 0:
            for row in list(report.get("errors") or [])[:10]:
                print(f"{row.get('code')} {row.get('where')} {row.get('detail')}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
