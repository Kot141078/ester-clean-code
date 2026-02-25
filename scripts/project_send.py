# -*- coding: utf-8 -*-
"""scripts/project_send.py - CLI: sformirovat konvert i otpravit (LAN/Telegram).

Primer:
  python -m scripts.project_send --mode lan --ttl 3600\
    --project-id P1 --name "Demo" --summary "..." --data-file /path/data.json

Mosty:
- Yavnyy (Kibernetika ↔ Svyaz): konvert + transport, bez UI.
- Skrytyy 1 (Infoteoriya ↔ CLI): strogiy JSON-vyvod (dlya payplaynov).
- Skrytyy 2 (Praktika ↔ Bezopasnost): TTL po umolchaniyu; HMAC pri nalichii secreta.

Zemnoy abzats:
Udobno “v pole”: sobrat i otoslat proekt s servera bez brauzera.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from modules.transport.project_envelope import make_envelope  # type: ignore
from modules.transport.transport_manager import send_project  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SELF_NODE_ID = os.getenv("HOSTNAME") or os.getenv("COMPUTERNAME") or "node"
SELF_BASE = os.getenv("ESTER_HTTP_BASE", "http://127.0.0.1:8080").strip()

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Project Send")
    ap.add_argument("--mode", choices=["lan", "telegram"], required=True)
    ap.add_argument("--ttl", type=int, default=3600)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--summary", default="")
    ap.add_argument("--tags", default="", help="separated by commas")
    ap.add_argument("--data-file", default="", help="put k JSON")
    args = ap.parse_args(argv)

    data = {}
    if args.data_file:
        data = json.loads(Path(args.data_file).read_text(encoding="utf-8"))

    project = {
        "id": args.project_id,
        "name": args.name,
        "summary": args.summary,
        "tags": [t.strip() for t in args.tags.split(",")] if args.tags else [],
        "data": data,
    }
    env = make_envelope(SELF_NODE_ID, SELF_BASE, project=project, ttl=args.ttl)
    rep = send_project(mode=args.mode, envelope=env)

    print(json.dumps({"ok": bool(rep.get("ok")), "send_result": rep, "envelope": env}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())