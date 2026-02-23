# -*- coding: utf-8 -*-
"""
scripts/restore_drill.py — drill-protsedura vosstanovleniya.
Povedenie:
  * Ischet posledniy *.enc v BACKUP_DIR
  * verify → restore v TEMP_TARGET (ili ukazannuyu)
  * Po umolchaniyu vypolnyaet odin prokhod. Dlya tsiklicheskogo progona ustanovite DRILL_INTERVAL_SEC>0.

ENV:
  PERSIST_DIR
  BACKUP_DIR
  BACKUP_HMAC_KEY
  TEMP_TARGET            — tselevaya papka vosstanovleniya (po umolchaniyu PERSIST_DIR/_drill_restore)
  DRILL_INTERVAL_SEC     — interval v sekundakh (0 → odin prokhod)
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict

import requests


def _persist_dir() -> str:
    return os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))


def _backup_dir() -> str:
    p = os.getenv("BACKUP_DIR") or os.path.join(_persist_dir(), "backups")
    os.makedirs(p, exist_ok=True)
    return p


def _latest_backup() -> str | None:
    cands = [
        os.path.join(_backup_dir(), f) for f in os.listdir(_backup_dir()) if f.endswith(".enc")
    ]
    if not cands:
        return None
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands[0]


def _run_once() -> int:
    from routes.backup_routes import _key  # reuse key resolution

    key = _key()
    if not key:
        print("No BACKUP_HMAC_KEY configured")
        return 2
    path = _latest_backup()
    if not path:
        print("No backups found")
        return 1
    # verify
    from routes.backup_routes import _alg

    env = json.load(open(path, "r", encoding="utf-8"))
    payload_b64 = env.get("payload_b64") or ""
    from security.signing import hmac_hex

    ok = hmac_hex(payload_b64.encode("utf-8"), key, alg=_alg()) == env.get("hmac")
    print("verify:", ok)
    if not ok:
        return 3
    # restore
    target = os.getenv("TEMP_TARGET") or os.path.join(_persist_dir(), "_drill_restore")
    import base64
    import io
    import zipfile

    from routes.backup_routes import _xor

    enc = base64.b64decode(payload_b64.encode("ascii"))
    nonce_b = None
    try:
        import base64 as _b64

        nonce_b = _b64.b64decode((env.get("nonce") or "").encode("ascii"))
    except Exception:
        nonce_b = b""
    zip_bytes = _xor(enc, key + (nonce_b or b""))
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
        z.extractall(target)
    print("restore to:", target)
    return 0


def _request_auth_token(session: requests.Session, base: str) -> tuple[str | None, requests.Response | None]:
    env_token = os.getenv("AUTH_JWT")
    if env_token:
        return env_token, None
    username = os.getenv("USER_NAME") or os.getenv("ESTER_BACKUP_USER")
    password = os.getenv("USER_PASS") or os.getenv("ESTER_BACKUP_PASS")
    if not username or not password:
        return None, None
    resp = session.post(
        f"{base.rstrip('/')}/auth/token",
        json={"username": username, "password": password},
        timeout=15,
    )
    if resp.status_code != 200:
        return None, resp
    data = {}
    try:
        data = resp.json()
    except Exception:
        data = {}
    return str(data.get("token") or ""), resp


def run_once() -> Dict[str, Any]:
    """
    Remote drill runner used by tests: requests auth token and triggers /ops/backup/restore.
    """
    base = os.getenv("API_BASE")
    if not base:
        return {"ok": False, "error": "API_BASE is not set", "status": 400}
    session = requests.Session()
    token, auth_resp = _request_auth_token(session, base)
    if not token:
        status = getattr(auth_resp, "status_code", 0)
        return {"ok": False, "status": status or 401, "error": "auth failed"}
    resp = session.post(
        f"{base.rstrip('/')}/ops/backup/restore",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    data = {}
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text}
    return {"ok": resp.status_code == 200, "status": resp.status_code, "response": data}


def main() -> int:
    interval = int(float(os.getenv("DRILL_INTERVAL_SEC", "0")))
    if interval <= 0:
        return _run_once()
    while True:
        rc = _run_once()
        print("drill rc:", rc)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
