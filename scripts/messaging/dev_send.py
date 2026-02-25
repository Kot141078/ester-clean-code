# -*- coding: utf-8 -*-
"""scripts/messaging/dev_send.py - lokalnaya otpravka soobscheniy (bez seti po umolchaniyu).

MOSTY:
- (Yavnyy) CLI: --to telegram|whatsapp, --chat <id>, --text <msg>.
- (Skrytyy #1) Esli ENV DEV_DRYRUN=1 — vyvodim sobrannyy payload vmesto setevogo vyzova.
- (Skrytyy #2) Prigodno dlya smoke-check pri pustykh tokenakh.

ZEMNOY ABZATs:
Bystro proverit, “what by ushlo” v kanal, ne riskuya realno otpravit.

# c=a+b"""
from __future__ import annotations

import argparse
import json
import os

from messaging.telegram_adapter import TelegramAdapter
from messaging.whatsapp_adapter import WhatsAppAdapter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", choices=["telegram","whatsapp"], required=True)
    ap.add_argument("--chat", required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()

    if args.to == "telegram":
        if os.getenv("DEV_DRYRUN","1") == "1":
            print(json.dumps({"chat_id": args.chat, "text": args.text}, ensure_ascii=False))
            return
        print(TelegramAdapter().send_message(args.chat, args.text))
    else:
        if os.getenv("DEV_DRYRUN","1") == "1":
            print(json.dumps({"to": args.chat, "text": args.text}, ensure_ascii=False))
            return
        print(WhatsAppAdapter().send_text(args.chat, args.text))

if __name__ == "__main__":
    main()