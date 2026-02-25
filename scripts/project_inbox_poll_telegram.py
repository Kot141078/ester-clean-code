# -*- coding: utf-8 -*-
"""scripts/project_inbox_poll_telegram.py - podtyagivaet konverty iz Telegram i kladet v inboxes (B).

CLI:
  python -m scripts.project_inbox_poll_telegram --once --ttl 3600
  python -m scripts.project_inbox_poll_telegram --loop --ttl 3600

Mosty:
- Yavnyy (Svyaz ↔ Ekspluatatsiya): fallback-priem cherez Telegram pri otsutstvii LAN.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): filtruem tolko t=='project', proveryaem TTL/HMAC.
- Skrytyy 2 (Praktika ↔ Nadezhnost): loop-bezopasnyy, bez zavisimostey.

Zemnoy abzats:
Eto “pochtalon iz messendzhera”: vidit konverty v chate i, esli vse validno, zanosit v inboxes (B).

# c=a+b"""
from __future__ import annotations

import argparse
import json
import sys
import time

from modules.transport.telegram_bridge import get_updates  # type: ignore
from modules.transport.project_inbox import validate_and_store  # type: ignore
from modules.transport.project_envelope import verify_envelope  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _extract_envelopes(upd_payload: dict) -> list[dict]:
    out = []
    for it in (upd_payload.get("result") or []):
        msg = (it.get("message") or it.get("channel_post") or {})
        txt = msg.get("text") or ""
        if txt.strip().startswith("```") and txt.strip().endswith("```"):
            # format iz send_json: fenced JSON
            txt = txt.strip()[3:-3]
        try:
            j = json.loads(txt)
        except Exception:
            continue
        if isinstance(j, dict) and j.get("t") == "project":
            out.append(j)
    return out

def once(ttl_override: int | None = None) -> int:
    up = get_updates(timeout=5)
    if not up.get("ok"):
        print(json.dumps({"ok": False, "error": "telegram-getUpdates-failed", "payload": up.get("payload")}, ensure_ascii=False))
        return 1
    envs = _extract_envelopes(up.get("payload") or {})
    results = []
    for e in envs:
        if ttl_override:
            e["ttl"] = int(ttl_override)
        v = verify_envelope(e)
        if not v.get("ok"):
            results.append({"ok": False, "reason": v.get("reason"), "unsigned": v.get("unsigned", False)})
            continue
        res = validate_and_store(e)
        results.append(res)
    print(json.dumps({"ok": True, "count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0

def loop(ttl_override: int | None = None) -> int:
    while True:
        try:
            once(ttl_override=ttl_override)
            time.sleep(5)
        except KeyboardInterrupt:
            return 0

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Telegram Inbox Poller")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    ap.add_argument("--ttl", type=int, default=0, help="replace incoming TTL (sec)")
    args = ap.parse_args(argv)
    ttl_o = int(args.ttl) if args.ttl > 0 else None
    return once(ttl_o) if args.once else loop(ttl_o)

if __name__ == "__main__":
    raise SystemExit(main())