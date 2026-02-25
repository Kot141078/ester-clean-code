# -*- coding: utf-8 -*-
"""scripts/messaging/set_telegram_commands.py - ustanovka Bot API komand.

MOSTY:
- (Yavnyy) Registriruet set: /start, /stop, /help, /silence, /resume.
- (Skrytyy #1) --dry vyvodit payload bez obrascheniya k seti; DEV_DRYRUN=1 - analogical.
- (Skrytyy #2) Podskazki pomogayut “ne pugat”: myagkie formulirovki.

ZEMNOY ABZATs:
Komandy vidny polzovatelyu i zadayut ozhidaniya: kak vklyuchit/vyklyuchit proaktivnost i chto bot umeet.

# c=a+b"""
from __future__ import annotations

import argparse, json, os, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

API = "https://api.telegram.org/bot{token}/setMyCommands"

CMDS = [
  {"command":"start","description":"connect an assistant"},
  {"command":"stop","description":"turn off notifications"},
  {"command":"help","description":"what can I do"},
  {"command":"silence","description":"tikhiy rezhim na chas"},
  {"command":"resume","description":"remove quiet mode"},
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.getenv("TG_BOT_TOKEN",""), help="Bot token")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    if not args.token:
        print("TG_BOT_TOKEN not set")
        return
    payload = {"commands": CMDS, "language_code": args.lang}
    if args.dry or os.getenv("DEV_DRYRUN","0")=="1":
        print(json.dumps(payload, ensure_ascii=False, indent=2)); return
    req = urllib.request.Request(API.format(token=args.token),
        data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:  # nosec
        print(r.read().decode("utf-8", errors="ignore"))

if __name__ == "__main__":
    main()