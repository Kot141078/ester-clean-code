# -*- coding: utf-8 -*-
"""
scripts/replication_apply.py — otpravka ZIP na /replication/apply s HMAC-podpisyu.
ENV:
  API_BASE (http://127.0.0.1:8080)
  AUTH_JWT (optsionalno)
  REPLICATION_HMAC_KEY ili REPLICATION_HMAC_KEY_FILE
Primer:
  REPLICATION_HMAC_KEY=secret python scripts/replication_apply.py snap.zip
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from security.signing import header_signature  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _read_key() -> Optional[bytes]:
    k = os.getenv("REPLICATION_HMAC_KEY")
    if k:
        return k.encode("utf-8")
    kf = os.getenv("REPLICATION_HMAC_KEY_FILE")
    if kf and os.path.exists(kf):
        return open(kf, "rb").read().strip()
    return None


def main():
    try:
        import requests  # type: ignore
    except Exception:
        print("requests not installed", file=sys.stderr)
        sys.exit(2)
    base = (os.getenv("API_BASE") or "http://127.0.0.1:8080").rstrip("/")
    if len(sys.argv) < 2:
        print("usage: python scripts/replication_apply.py <zip_path>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        print("file not found: " + path, file=sys.stderr)
        sys.exit(2)
    key = _read_key()
    if not key:
        print("no REPLICATION_HMAC_KEY or REPLICATION_HMAC_KEY_FILE", file=sys.stderr)
        sys.exit(2)
    data = open(path, "rb").read()
    sig = header_signature(data, key)

    headers = {"Content-Type": "application/zip", "X-Signature": sig}
    jwt = os.getenv("AUTH_JWT")
    if jwt:
        headers["Authorization"] = "Bearer " + jwt

    r = requests.post(base + "/replication/apply", data=data, headers=headers, timeout=60)
    try:
        j = r.json()
    except Exception:
        j = {"status_code": r.status_code}
    print(json.dumps({"status": r.status_code, "response": j}, ensure_ascii=False))
    sys.exit(0 if r.status_code == 200 else 1)


if __name__ == "__main__":
    main()