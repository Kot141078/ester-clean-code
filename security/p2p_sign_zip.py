# -*- coding: utf-8 -*-
"""
scripts/p2p_sign_zip.py — utilita podpisi ZIP dlya replikatsii.
Ispolzuet klyuch iz ENV REPLICATION_HMAC_KEY ili iz fayla (ENV REPLICATION_HMAC_KEY_FILE).
Primer:
  REPLICATION_HMAC_KEY=secret python scripts/p2p_sign_zip.py snapshot.zip
Vyvodit JSON: {"X-Signature": "...", "b64": "...", "hex": "..."}
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from security.signing import header_signature, sign  # type: ignore
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
    if len(sys.argv) < 2:
        print("usage: python scripts/p2p_sign_zip.py <zip_path>", file=sys.stderr)
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
    b64 = sign(data, key, out="b64")
    hx = sign(data, key, out="hex")
    hdr = header_signature(data, key)
    print(json.dumps({"X-Signature": hdr, "b64": b64, "hex": hx}, ensure_ascii=False))


if __name__ == "__main__":
    main()
