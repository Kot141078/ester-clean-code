# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import bundle_signing, publisher_roster, publisher_transparency_log


def _write_json(path: Path, payload: Dict[str, Any], *, canonical: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if canonical:
        path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _persist_dir(raw: str) -> Path:
    if str(raw or "").strip():
        p = Path(str(raw or "").strip()).resolve()
    else:
        env = str(os.getenv("PERSIST_DIR") or "").strip()
        if env:
            p = Path(env).resolve()
        else:
            p = (ROOT / "data").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_roster_root_keys(ns: argparse.Namespace, persist_dir: Path) -> Dict[str, str]:
    priv_raw = str(getattr(ns, "roster_root_privkey", "") or os.getenv("ESTER_ROSTER_ROOT_PRIVKEY_PATH") or "").strip()
    pub_raw = str(getattr(ns, "roster_root_pubkey", "") or os.getenv("ESTER_ROSTER_ROOT_PUBKEY_PATH") or "").strip()

    priv = ""
    pub = ""
    if priv_raw:
        p = Path(priv_raw)
        priv = str(p.resolve() if p.is_absolute() else (persist_dir / p).resolve())
    if pub_raw:
        p = Path(pub_raw)
        pub = str(p.resolve() if p.is_absolute() else (persist_dir / p).resolve())
    return {"priv": priv, "pub": pub}


def _load_existing_roster(path: Path) -> Dict[str, Any]:
    loaded = publisher_roster.load_roster(str(path))
    if not bool(loaded.get("ok")):
        return {"ok": False, "error_code": str(loaded.get("error_code") or "ROSTER_REQUIRED"), "error": str(loaded.get("error") or "roster_load_failed")}
    roster = publisher_roster.normalize_roster(dict(loaded.get("roster") or {}))
    return {"ok": True, "roster": roster}


def _resolve_pub_path_for_roster(roster_path: Path, pubkey_input: str) -> Dict[str, Any]:
    raw = str(pubkey_input or "").strip()
    if not raw:
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "pubkey_path_required"}
    roster_root = publisher_roster.roster_root_dir(str(roster_path))
    p = Path(raw)
    abs_path = p.resolve() if p.is_absolute() else (roster_root / p).resolve()
    if not _path_within(abs_path, roster_root):
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "pubkey_path_forbidden"}
    if not abs_path.exists() or not abs_path.is_file():
        return {"ok": False, "error_code": "PUBLISHER_PUBKEY_MISSING", "error": "pubkey_file_missing"}
    rel = str(abs_path.relative_to(roster_root)).replace("\\", "/")
    fp = bundle_signing.pub_fingerprint_from_path(str(abs_path))
    if not fp:
        return {"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "pubkey_invalid"}
    return {"ok": True, "abs_path": str(abs_path), "rel_path": rel, "pub_fingerprint": fp}


def _upsert_key(rows: List[Dict[str, Any]], item: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    key_id = str(item.get("key_id") or "")
    replaced = False
    for row in rows:
        if str(dict(row).get("key_id") or "") == key_id:
            out.append(dict(item))
            replaced = True
        else:
            out.append(dict(row))
    if not replaced:
        out.append(dict(item))
    return sorted(out, key=lambda r: str(r.get("key_id") or ""))


def _sign_roster_only(roster: Dict[str, Any], root_priv: str, root_pub: str) -> Dict[str, Any]:
    now_ts = int(time.time())
    src = publisher_roster.normalize_roster(dict(roster or {}))
    if _to_int(src.get("created_ts"), 0) <= 0:
        src["created_ts"] = now_ts
    src["updated_ts"] = now_ts
    signed = publisher_roster.sign_roster(
        src,
        roster_root_privkey_path=root_priv,
        roster_root_pubkey_path=root_pub,
        key_id="roster-root",
    )
    if not bool(signed.get("ok")):
        return {
            "ok": False,
            "error_code": str(signed.get("error_code") or "ROSTER_SIG_INVALID"),
            "error": str(signed.get("error") or "roster_sign_failed"),
        }
    final = dict(signed.get("roster") or {})
    return {
        "ok": True,
        "roster": final,
        "roster_id": str(final.get("roster_id") or ""),
        "body_sha256": str(signed.get("body_sha256") or publisher_roster.compute_body_sha256(final)),
    }


def _publish_temp_roster(
    temp_roster_path: Path,
    *,
    persist_dir: Path,
    root_priv: str,
    root_pub: str,
    op: str,
    reason: str,
    strict: bool,
) -> Dict[str, Any]:
    keys_dir = (persist_dir / "keys").resolve()
    keys_dir.mkdir(parents=True, exist_ok=True)

    if not _path_within(temp_roster_path, persist_dir):
        return {"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_path_forbidden"}

    roster_obj = publisher_roster.normalize_roster(_load_json(temp_roster_path))
    verify_roster = publisher_roster.verify_roster_sig(roster_obj, str(root_pub))
    warnings: List[str] = []
    if not bool(verify_roster.get("ok")):
        if strict:
            return {
                "ok": False,
                "error_code": str(verify_roster.get("error_code") or "ROSTER_SIG_INVALID"),
                "error": str(verify_roster.get("error") or "roster_sig_invalid"),
            }
        warnings.append(f"roster_sig_warning:{verify_roster.get('error_code') or 'ROSTER_SIG_INVALID'}")

    body_sha = publisher_roster.compute_body_sha256(roster_obj)
    ts = int(time.time())
    pub_dir = (keys_dir / "roster_publications" / f"{ts}_{body_sha[:8]}").resolve()
    if not _path_within(pub_dir, persist_dir):
        return {"ok": False, "error_code": "LOG_PUBLICATION_MISSING", "error": "publication_path_forbidden"}
    pub_dir.mkdir(parents=True, exist_ok=True)
    pub_roster = (pub_dir / "publisher_roster.json").resolve()
    _write_json(pub_roster, roster_obj, canonical=True)
    pub_sha = hashlib.sha256(pub_roster.read_bytes()).hexdigest()
    (pub_dir / "publisher_roster.sha256").write_text(pub_sha + "\n", encoding="utf-8")
    publication_rel = str(pub_roster.relative_to(persist_dir)).replace("\\", "/")

    log_path = (keys_dir / "publisher_roster_log.jsonl").resolve()
    head_path = (keys_dir / "publisher_roster_log_head.json").resolve()

    if log_path.exists():
        verify_log = publisher_transparency_log.verify_log_chain(
            str(log_path),
            str(root_pub),
            require_strict_append=True,
            require_publications=True,
        )
        if not bool(verify_log.get("ok")):
            return {
                "ok": False,
                "error_code": str(verify_log.get("error_code") or "LOG_CHAIN_BROKEN"),
                "error": str(verify_log.get("error") or "log_verify_failed"),
            }
        prev_hash = str(verify_log.get("last_entry_hash") or "")
        entries_count = int(verify_log.get("entries_count") or 0)
    else:
        prev_hash = ""
        entries_count = 0

    entry: Dict[str, Any] = {
        "schema": publisher_transparency_log.ENTRY_SCHEMA_V1,
        "ts": ts,
        "roster_id": str(roster_obj.get("roster_id") or ""),
        "op": str(op or "update"),
        "reason": str(reason or ""),
        "body_sha256": body_sha,
        "roster_sig": dict(roster_obj.get("sig") or {}),
        "publication": {
            "relpath": publication_rel,
            "sha256": pub_sha,
        },
        "prev_hash": str(prev_hash or ""),
    }
    entry_hash = publisher_transparency_log.compute_entry_hash(entry)
    entry["entry_hash"] = entry_hash
    sig_entry = publisher_transparency_log.sign_entry_hash(entry_hash, root_priv, root_pub)
    if not bool(sig_entry.get("ok")):
        return {
            "ok": False,
            "error_code": str(sig_entry.get("error_code") or "LOG_SIG_INVALID"),
            "error": str(sig_entry.get("error") or "log_sig_invalid"),
        }
    entry["sig_entry"] = dict(sig_entry.get("sig_entry") or {})

    appended = publisher_transparency_log.append_entry(str(log_path), entry)
    if not bool(appended.get("ok")):
        return {"ok": False, "error_code": "LOG_CHAIN_BROKEN", "error": "log_append_failed"}

    head = publisher_transparency_log.update_head(str(head_path), entry_hash, entries_count + 1, ts)
    if not bool(head.get("ok")):
        return {"ok": False, "error_code": "LOG_CHAIN_BROKEN", "error": "head_update_failed"}

    return {
        "ok": True,
        "entry_hash": entry_hash,
        "prev_hash": str(prev_hash or ""),
        "body_sha256": body_sha,
        "publication_relpath": publication_rel,
        "log_path": str(log_path),
        "head_path": str(head_path),
        "warnings": warnings,
    }


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _mutate_and_write(
    *,
    roster_path: Path,
    roster_payload: Dict[str, Any],
    root_keys: Dict[str, str],
    persist_dir: Path,
    publish_log: bool,
    publish_strict: bool,
    op: str,
    reason: str,
) -> Dict[str, Any]:
    sign_rep = _sign_roster_only(roster_payload, root_keys["priv"], root_keys["pub"])
    if not bool(sign_rep.get("ok")):
        return sign_rep

    signed_roster = dict(sign_rep.get("roster") or {})
    tmp_path = roster_path.with_name(roster_path.name + f".tmp.{os.getpid()}.{int(time.time()*1000)}")
    _write_json(tmp_path, signed_roster, canonical=False)

    publish_rep: Dict[str, Any] = {"ok": True}
    if publish_log:
        publish_rep = _publish_temp_roster(
            tmp_path,
            persist_dir=persist_dir,
            root_priv=str(root_keys["priv"]),
            root_pub=str(root_keys["pub"]),
            op=str(op or "update"),
            reason=str(reason or ""),
            strict=bool(publish_strict),
        )
        if not bool(publish_rep.get("ok")):
            _safe_unlink(tmp_path)
            return publish_rep

    roster_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(tmp_path), str(roster_path))

    out = {
        "ok": True,
        "roster_path": str(roster_path),
        "roster_id": str(signed_roster.get("roster_id") or ""),
        "body_sha256": str(sign_rep.get("body_sha256") or publisher_roster.compute_body_sha256(signed_roster)),
        "published": bool(publish_log),
        "publish": publish_rep if publish_log else {},
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Manage publisher roster (init/add/retire/revoke/show)")
    ap.add_argument("--publish-log", action="store_true")
    ap.add_argument("--no-publish-log", action="store_true")
    ap.add_argument("--persist-dir", default="")
    ap.add_argument("--op", default="")
    ap.add_argument("--reason", default="")

    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--out", required=True)
    p_init.add_argument("--threshold", type=int, default=2)
    p_init.add_argument("--of", type=int, default=3)
    p_init.add_argument("--roster-id", required=True)
    p_init.add_argument("--roster-root-privkey", default="")
    p_init.add_argument("--roster-root-pubkey", default="")

    p_add = sub.add_parser("add-key")
    p_add.add_argument("--roster", required=True)
    p_add.add_argument("--key-id", required=True)
    p_add.add_argument("--pubkey", required=True)
    p_add.add_argument("--status", default="active")
    p_add.add_argument("--not-before-ts", type=int, default=0)
    p_add.add_argument("--not-after-ts", type=int, default=0)
    p_add.add_argument("--comment", default="")
    p_add.add_argument("--roster-root-privkey", default="")
    p_add.add_argument("--roster-root-pubkey", default="")

    p_retire = sub.add_parser("retire-key")
    p_retire.add_argument("--roster", required=True)
    p_retire.add_argument("--key-id", required=True)
    p_retire.add_argument("--not-after-ts", type=int, default=0)
    p_retire.add_argument("--roster-root-privkey", default="")
    p_retire.add_argument("--roster-root-pubkey", default="")

    p_revoke = sub.add_parser("revoke-key")
    p_revoke.add_argument("--roster", required=True)
    p_revoke.add_argument("--key-id", required=True)
    p_revoke.add_argument("--revoked-ts", type=int, default=0)
    p_revoke.add_argument("--reason", default="")
    p_revoke.add_argument("--roster-root-privkey", default="")
    p_revoke.add_argument("--roster-root-pubkey", default="")

    p_show = sub.add_parser("show")
    p_show.add_argument("--roster", required=True)

    ns = ap.parse_args()

    slot = _slot()
    persist_dir = _persist_dir(str(ns.persist_dir or ""))
    warnings: List[str] = []

    publish_log = True
    if bool(ns.no_publish_log):
        publish_log = False
    if bool(ns.publish_log):
        publish_log = True
    if slot == "B":
        if bool(ns.no_publish_log):
            warnings.append("publish_log_forced_in_slot_b")
        publish_log = True
    publish_strict = bool(slot == "B")

    if ns.cmd == "show":
        roster_path = Path(str(ns.roster)).resolve()
        loaded = _load_existing_roster(roster_path)
        if not bool(loaded.get("ok")):
            print(json.dumps(loaded, ensure_ascii=True, indent=2))
            return 2
        roster = dict(loaded.get("roster") or {})
        out = {
            "ok": True,
            "roster_path": str(roster_path),
            "roster": roster,
            "body_sha256": publisher_roster.compute_body_sha256(roster),
            "warnings": warnings,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0

    root_keys = _resolve_roster_root_keys(ns, persist_dir)
    if (not root_keys["priv"]) or (not root_keys["pub"]):
        print(json.dumps({"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_keys_missing"}, ensure_ascii=True, indent=2))
        return 2
    root_priv_path = Path(str(root_keys["priv"])).resolve()
    root_pub_path = Path(str(root_keys["pub"])).resolve()
    if (not root_priv_path.exists()) or (not root_priv_path.is_file()) or (not root_pub_path.exists()) or (not root_pub_path.is_file()):
        print(json.dumps({"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_keys_missing"}, ensure_ascii=True, indent=2))
        return 2
    if (not _path_within(root_priv_path, persist_dir)) or (not _path_within(root_pub_path, persist_dir)):
        print(json.dumps({"ok": False, "error_code": "ROSTER_ROOT_PUBKEY_REQUIRED", "error": "roster_root_key_path_forbidden"}, ensure_ascii=True, indent=2))
        return 2

    if ns.cmd == "init":
        roster_path = Path(str(ns.out)).resolve()
        if publish_log and (not _path_within(roster_path, persist_dir)):
            print(json.dumps({"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_path_forbidden"}, ensure_ascii=True, indent=2))
            return 2
        roster = {
            "schema": publisher_roster.ROSTER_SCHEMA_V1,
            "created_ts": int(time.time()),
            "updated_ts": int(time.time()),
            "roster_id": str(ns.roster_id or ""),
            "policy": {
                "schema": "ester.publisher.policy.v1",
                "threshold": max(1, int(ns.threshold or 2)),
                "of": max(1, int(ns.of or 3)),
                "allow_legacy_single_sig": True,
            },
            "keys": [],
        }
        if int(roster["policy"]["threshold"]) > int(roster["policy"]["of"]):
            print(json.dumps({"ok": False, "error_code": "MULTISIG_THRESHOLD_NOT_MET", "error": "threshold_gt_of"}, ensure_ascii=True, indent=2))
            return 2
        op = str(ns.op or "init")
        reason = str(ns.reason or "")
        rep = _mutate_and_write(
            roster_path=roster_path,
            roster_payload=roster,
            root_keys=root_keys,
            persist_dir=persist_dir,
            publish_log=publish_log,
            publish_strict=publish_strict,
            op=op,
            reason=reason,
        )
        rep["warnings"] = warnings + list(rep.get("warnings") or [])
        print(json.dumps(rep, ensure_ascii=True, indent=2))
        return 0 if bool(rep.get("ok")) else 2

    roster_path = Path(str(getattr(ns, "roster", ""))).resolve()
    if publish_log and (not _path_within(roster_path, persist_dir)):
        print(json.dumps({"ok": False, "error_code": "ROSTER_REQUIRED", "error": "roster_path_forbidden"}, ensure_ascii=True, indent=2))
        return 2

    loaded = _load_existing_roster(roster_path)
    if not bool(loaded.get("ok")):
        print(json.dumps(loaded, ensure_ascii=True, indent=2))
        return 2
    roster = dict(loaded.get("roster") or {})

    op = str(ns.op or "update")
    reason = str(ns.reason or "")

    if ns.cmd == "add-key":
        resolved_pub = _resolve_pub_path_for_roster(roster_path, str(ns.pubkey or ""))
        if not bool(resolved_pub.get("ok")):
            print(json.dumps(resolved_pub, ensure_ascii=True, indent=2))
            return 2
        item = {
            "key_id": str(ns.key_id or "").strip(),
            "pub_path": str(resolved_pub.get("rel_path") or ""),
            "pub_fingerprint": str(resolved_pub.get("pub_fingerprint") or ""),
            "status": str(ns.status or "active").strip().lower(),
            "not_before_ts": int(ns.not_before_ts or 0),
            "not_after_ts": int(ns.not_after_ts or 0),
            "revoked_ts": 0,
            "comment": str(ns.comment or ""),
        }
        roster["keys"] = _upsert_key([dict(x) for x in list(roster.get("keys") or []) if isinstance(x, dict)], item)
        if not op:
            op = "update"

    elif ns.cmd == "retire-key":
        key_id = str(ns.key_id or "").strip()
        rows = [dict(x) for x in list(roster.get("keys") or []) if isinstance(x, dict)]
        hit = False
        for row in rows:
            if str(row.get("key_id") or "").strip() != key_id:
                continue
            hit = True
            row["status"] = "retired"
            row["not_after_ts"] = int(ns.not_after_ts or int(time.time()))
        if not hit:
            print(json.dumps({"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "roster_key_unknown", "key_id": key_id}, ensure_ascii=True, indent=2))
            return 2
        roster["keys"] = sorted(rows, key=lambda r: str(r.get("key_id") or ""))
        if not op:
            op = "retire"

    elif ns.cmd == "revoke-key":
        key_id = str(ns.key_id or "").strip()
        rows = [dict(x) for x in list(roster.get("keys") or []) if isinstance(x, dict)]
        hit = False
        for row in rows:
            if str(row.get("key_id") or "").strip() != key_id:
                continue
            hit = True
            row["status"] = "revoked"
            row["revoked_ts"] = int(ns.revoked_ts or int(time.time()))
            reason_row = str(ns.reason or "").strip()
            if reason_row:
                base_comment = str(row.get("comment") or "").strip()
                row["comment"] = f"{base_comment}; {reason_row}".strip("; ").strip()
        if not hit:
            print(json.dumps({"ok": False, "error_code": "ROSTER_KEY_UNKNOWN", "error": "roster_key_unknown", "key_id": key_id}, ensure_ascii=True, indent=2))
            return 2
        roster["keys"] = sorted(rows, key=lambda r: str(r.get("key_id") or ""))
        if not op:
            op = "revoke"

    else:
        print(json.dumps({"ok": False, "error": "unsupported_command"}, ensure_ascii=True, indent=2))
        return 2

    rep = _mutate_and_write(
        roster_path=roster_path,
        roster_payload=roster,
        root_keys=root_keys,
        persist_dir=persist_dir,
        publish_log=publish_log,
        publish_strict=publish_strict,
        op=op,
        reason=reason,
    )
    rep["warnings"] = warnings + list(rep.get("warnings") or [])
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
