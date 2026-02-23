# -*- coding: utf-8 -*-
"""
scripts/p2p_send_cli.py — polozhit «konvert» v outbox i initsiirovat otpravku (Telegram).

Primer:
  AB_MODE=B python -m scripts.p2p_send_cli --project MyProj --profile default --note "hello"

Flagi:
  --project <name>     — logicheskoe imya proekta (string)
  --profile <id>       — sync_profile_id (string)
  --note "<text>"      — komment v payload (opts.)

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): unifitsirovannaya otpravka «kak UI», no iz CLI.
- Skrytyy 1 (Infoteoriya ↔ Diagnostika): pechataet itogovyy put i rezultat send().
- Skrytyy 2 (Praktika ↔ Sovmestimost): envelope identichen LAN/USB.

Zemnoy abzats:
Eto «otpravit pismo iz konsoli»: polozhil v outbox — kurer zabral i dones v chat.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
import time

from modules.transport.p2p_settings import load_settings  # type: ignore
from modules.transport.spool import put_outbox  # type: ignore
from modules.transport.telegram_driver import send_envelope  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester P2P send")
    ap.add_argument("--project", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)

    env = {
        "type": "p2p_env",
        "ts": int(time.time()),
        "src": {"node": "local"},
        "sig": "",
        "payload": {"project": args.project, "sync_profile_id": args.profile, "note": args.note},
    }
    path = put_outbox(env)
    s = load_settings()
    rep = send_envelope(env, s, ab_mode=AB) if s.get("enable") else {"ok": False, "reason": "p2p-disabled"}
    print(json.dumps({"ok": rep.get("ok", False), "path": path, "send": rep}, ensure_ascii=False, indent=2))
    return 0 if rep.get("ok", False) else 1

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b