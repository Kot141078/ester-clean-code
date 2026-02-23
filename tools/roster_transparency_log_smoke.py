# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import l4w_witness


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists() or not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(dict(obj))
    return out


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
    return payload


def _run_manage(env: Dict[str, str], args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, "-B", str((ROOT / "tools" / "publisher_roster_manage.py").resolve())] + list(args)
    return _run_json(cmd, env)


def _run_verify(env: Dict[str, str], args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, "-B", str((ROOT / "tools" / "auditor_verify_roster_log.py").resolve())] + list(args)
    return _run_json(cmd, env)


def _error_codes(rep: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for row in list(rep.get("errors") or []):
        if isinstance(row, dict):
            code = str(row.get("code") or "").strip()
            if code:
                out.append(code)
    return out


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_roster_log_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    keys_dir = (persist_dir / "keys").resolve()
    keys_dir.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "ESTER_VOLITION_SLOT",
        "ESTER_ROSTER_ROOT_PRIVKEY_PATH",
        "ESTER_ROSTER_ROOT_PUBKEY_PATH",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}

    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["ESTER_VOLITION_SLOT"] = "B"

    roster_path = (keys_dir / "publisher_roster.json").resolve()
    log_path = (keys_dir / "publisher_roster_log.jsonl").resolve()
    head_path = (keys_dir / "publisher_roster_log_head.json").resolve()
    root_priv = (keys_dir / "roster_root_private.pem").resolve()
    root_pub = (keys_dir / "roster_root_public.pem").resolve()
    pub_a = (keys_dir / "publisher-A_public.pem").resolve()
    pub_b = (keys_dir / "publisher-B_public.pem").resolve()

    try:
        rep_root = l4w_witness.ensure_keypair(priv_path=str(root_priv), pub_path=str(root_pub), overwrite=True)
        rep_a = l4w_witness.ensure_keypair(priv_path=str((keys_dir / "publisher-A_private.pem").resolve()), pub_path=str(pub_a), overwrite=True)
        rep_b = l4w_witness.ensure_keypair(priv_path=str((keys_dir / "publisher-B_private.pem").resolve()), pub_path=str(pub_b), overwrite=True)
        rep_c = l4w_witness.ensure_keypair(
            priv_path=str((keys_dir / "publisher-C_private.pem").resolve()),
            pub_path=str((keys_dir / "publisher-C_public.pem").resolve()),
            overwrite=True,
        )
        if not bool(rep_root.get("ok")) or not bool(rep_a.get("ok")) or not bool(rep_b.get("ok")) or not bool(rep_c.get("ok")):
            out = {"ok": False, "error": "keygen_failed", "rep_root": rep_root, "rep_a": rep_a, "rep_b": rep_b, "rep_c": rep_c}
            print(json.dumps(out, ensure_ascii=True, indent=2))
            return 2

        os.environ["ESTER_ROSTER_ROOT_PRIVKEY_PATH"] = str(root_priv)
        os.environ["ESTER_ROSTER_ROOT_PUBKEY_PATH"] = str(root_pub)
        env = dict(os.environ)

        init_rep = _run_manage(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--op",
                "init",
                "--reason",
                "smoke_init",
                "init",
                "--out",
                str(roster_path),
                "--threshold",
                "2",
                "--of",
                "3",
                "--roster-id",
                "roster-log-smoke",
                "--roster-root-privkey",
                str(root_priv),
                "--roster-root-pubkey",
                str(root_pub),
            ],
        )

        entries_after_init = _read_jsonl(log_path)
        head_after_init = _read_json(head_path)

        add_rep = _run_manage(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--op",
                "update",
                "--reason",
                "smoke_add",
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-A",
                "--pubkey",
                str(pub_a),
                "--status",
                "active",
                "--roster-root-privkey",
                str(root_priv),
                "--roster-root-pubkey",
                str(root_pub),
            ],
        )

        entries_after_add = _read_jsonl(log_path)
        chain_ok = False
        if len(entries_after_add) >= 2:
            first = dict(entries_after_add[0])
            second = dict(entries_after_add[1])
            chain_ok = (
                str(first.get("prev_hash") or "") == ""
                and str(second.get("prev_hash") or "") == str(first.get("entry_hash") or "")
            )

        verify_ok = _run_verify(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--pubkey-roster-root",
                str(root_pub),
                "--json",
            ],
        )

        roster_before_fail = roster_path.read_bytes() if roster_path.exists() else b""
        fail_closed = _run_manage(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--op",
                "update",
                "--reason",
                "smoke_fail_closed",
                "add-key",
                "--roster",
                str(roster_path),
                "--key-id",
                "publisher-B",
                "--pubkey",
                str(pub_b),
                "--status",
                "active",
                "--roster-root-privkey",
                str((keys_dir / "missing_roster_root_private.pem").resolve()),
                "--roster-root-pubkey",
                str(root_pub),
            ],
        )
        roster_after_fail = roster_path.read_bytes() if roster_path.exists() else b""
        fail_closed_ok = int(fail_closed.get("rc") or 0) == 2 and roster_before_fail == roster_after_fail

        tamper_done = False
        if len(entries_after_add) >= 2:
            tamper_pub_rel = str(dict(entries_after_add[1]).get("publication", {}).get("relpath") or "").strip()
            tamper_pub_file = (persist_dir / tamper_pub_rel).resolve() if tamper_pub_rel else Path("")
            if str(tamper_pub_file) and tamper_pub_file.exists() and tamper_pub_file.is_file():
                tamper_pub_file.write_bytes(tamper_pub_file.read_bytes() + b"\n")
                tamper_done = True

        verify_tampered = _run_verify(
            env,
            [
                "--persist-dir",
                str(persist_dir),
                "--pubkey-roster-root",
                str(root_pub),
                "--require-publications",
                "--json",
            ],
        )
        tamper_codes = _error_codes(verify_tampered)

        init_ok = (
            bool(init_rep.get("ok"))
            and len(entries_after_init) == 1
            and str(dict(entries_after_init[0]).get("prev_hash") or "") == ""
            and int(head_after_init.get("entries_count") or 0) == 1
            and str(head_after_init.get("last_entry_hash") or "") == str(dict(entries_after_init[0]).get("entry_hash") or "")
        )
        add_ok = bool(add_rep.get("ok")) and len(entries_after_add) >= 2 and bool(chain_ok)
        verify_ok_flag = int(verify_ok.get("rc") or 0) == 0
        tamper_ok = bool(tamper_done) and int(verify_tampered.get("rc") or 0) == 2 and ("LOG_PUBLICATION_SHA_MISMATCH" in tamper_codes)

        ok = bool(init_ok and add_ok and verify_ok_flag and tamper_ok and fail_closed_ok)
        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "persist_dir": str(persist_dir),
            "init": init_rep,
            "add": add_rep,
            "verify_ok": verify_ok,
            "verify_tampered": verify_tampered,
            "fail_closed": fail_closed,
            "checks": {
                "init_entry_and_head": bool(init_ok),
                "chain_prev_hash": bool(add_ok),
                "verify_pass": bool(verify_ok_flag),
                "tamper_fail": bool(tamper_ok),
                "slot_b_fail_closed": bool(fail_closed_ok),
            },
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
