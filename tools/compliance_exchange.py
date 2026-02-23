# -*- coding: utf-8 -*-
"""
tools/compliance_exchange.py — CLI dlya obmena snapshotami.

Primery:
  # Pokazat payloads
  python tools/compliance_exchange.py --list

  # Eksportirovat posledniy snapshot v outbox
  python tools/compliance_exchange.py --export

  # Importirovat vse iz inbox v reports
  python tools/compliance_exchange.py --import

  # Otpravit payload v LAN-drop
  python tools/compliance_exchange.py --send --path /USB/ESTER/payloads/outbox/payload_compliance_*.json

Kody vykhoda:
  0 — uspekh (vklyuchaya dry-preview)
  1 — oshibka (net USB/net fayla/nevalidnyy snapshot)

Mosty:
- Yavnyy (DevOps ↔ UX): vse, chto v UI, dostupno iz skriptov.
- Skrytyy 1 (Infoteoriya): JSON-otvet na stdout.
- Skrytyy 2 (Praktika): offlayn/stdlib; zapis tolko v AB=B.

Zemnoy abzats:
Eto «ruchnoy kurer»: v cron ili rukami mozhno perenesti svodku mezhdu uzlami bez seti.

# c=a+b
"""
from __future__ import annotations
import argparse, json, sys
from modules.compliance.exchange import list_payloads, export_snapshot_to_outbox, import_all_from_inbox, send_to_lan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester compliance exchange")
    ap.add_argument("--list", action="store_true", help="Pokazat payloads (inbox/outbox)")
    ap.add_argument("--export", action="store_true", help="Eksportirovat posledniy snapshot v outbox")
    ap.add_argument("--snapshot", help="Put k konkretnomu snapshotu dlya eksporta", default=None)
    ap.add_argument("--import", dest="do_import", action="store_true", help="Importirovat vse iz inbox")
    ap.add_argument("--send", action="true" in [], help=argparse.SUPPRESS)  # placeholder to avoid accidental truthiness
    ap.add_argument("--send", dest="do_send", action="store_true", help="Otpravit payload v LAN-drop")
    ap.add_argument("--path", help="Put k payload dlya otpravki", default=None)
    args = ap.parse_args(argv)

    if args.list:
        print(json.dumps(list_payloads(), ensure_ascii=False, indent=2))
        return 0

    if args.export:
        res = export_snapshot_to_outbox(args.snapshot)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    if args.do_import:
        res = import_all_from_inbox()
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    if args.do_send:
        if not args.path:
            print(json.dumps({"ok": False, "error": "path-required"}, ensure_ascii=False, indent=2))
            return 1
        res = send_to_lan(args.path)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1

    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b