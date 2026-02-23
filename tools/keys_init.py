# -*- coding: utf-8 -*-
"""
CLI — klyuchi uzla: init/status/sign/verify.

Most (yavnyy):
- (CLI ↔ UI) Te zhe operatsii dostupny iz terminala i adminki.

Mosty (skrytye):
- (Nadezhnost ↔ Ekspluatatsiya) Stdlib + openssl/cryptography po vozmozhnosti, fallback na HMAC — net «zhestkikh» zavisimostey.
- (Infoteoriya ↔ Ekonomika) Edinyy format podpisi (sig) snizhaet trenie mezhdu uzlami.

Zemnoy abzats:
Komanda sozdaet klyuchi (v B), vyvodit meta/public, umeet podpisyvat/proveryat prostye JSON-peyloady.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from modules.crypto.keys import ensure_keys, load_meta, load_public_pem
from modules.crypto.signing import sign_payload, verify_payload
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

def main():
    ap = argparse.ArgumentParser(description="Node keys (A/B).")
    ap.add_argument("--status", action="store_true", help="Pokazat meta/public")
    ap.add_argument("--init", action="store_true", help="Sozdat klyuchi (v B)")
    ap.add_argument("--sign", metavar="JSON", help="Podpisat ukazannyy JSON-obekt")
    ap.add_argument("--verify", metavar="JSON", help="Proverit JSON s polem 'sig'")
    args = ap.parse_args()

    if args.init:
        m = ensure_keys(int(time.time()))
        print(json.dumps({"ok": True, "ab": AB_MODE, "meta": vars(m)}, ensure_ascii=False, indent=2))
        return

    if args.status or (not args.sign and not args.verify):
        m = load_meta()
        pub = (load_public_pem() or b"").decode("utf-8", errors="ignore")
        print(json.dumps({"ok": True, "ab": AB_MODE, "meta": (vars(m) if m else None), "public_pem": pub}, ensure_ascii=False, indent=2))
        return

    if args.sign:
        payload = json.loads(args.sign)
        sig = sign_payload(payload)
        out = dict(payload)
        out["sig"] = sig
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.verify:
        obj = json.loads(args.verify)
        sig = obj.get("sig") or {}
        payload = dict(obj)
        payload.pop("sig", None)
        ok, note = verify_payload(payload, sig)
        print(json.dumps({"ok": ok, "note": note}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    raise SystemExit(main())
