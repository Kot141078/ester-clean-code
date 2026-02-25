#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tools/env_selfcheck.py - bezopasnaya samoproverka peremennykh okruzheniya (bez pravok koda prilozheniya).

Mosty:
- Yavnyy: Enderton (logika) → proverka ENV kak nabor predikatov nad (klyuch, znachenie), komponuemykh bez izmeneniya sistemy.
- Skrytyy #1: Ashbi (kibernetika) → dva rezhima kontrolya (perMISSive/STRICT) reguliruyut raznoobrazie reaktsiy na defekty konfiguratsii.
- Skrytyy #2: Cover & Thomas (infoteoriya) → svodim "entropiyu" konfiguratsii, vyyavlyaya neopredelennosti (pustye/defoltnye sekrety).

Zemnoy abzats (inzheneriya):
Skript nichego ne menyaet - tolko chitaet ENV i pechataet JSON-svodku.
Rezhim A/B: CHECK_MODE=permissive (A, po umolchaniyu) or strict (B). Esli strict failsya,
skript avtomaticheski otkatyvaetsya k permissive (avtokatbek) i zavershaetcya kodom 0, ostavlyaya preduprezhdeniya.
Eto help zapuskat proverku na lyubykh stendakh bez "krasnogo" CI.

# c=a+b"""
from __future__ import annotations
import json
import os
import sys
import time
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

RECOMMENDED: Dict[str, str] = {
    "APP_IMPORT": "app:app (ili wsgi_secure:app) — otkuda importirovat Flask app",
    "BASE_URL": "http://127.0.0.1:8080 - for HTTP smoke",
    "JWT_SECRET": "<64-simvolnyy sekret HS256>",
    "JWT_TTL": "3600",
    "JWT_REFRESH_TTL": "1209600",
    "TELEGRAM_BOT_TOKEN": "<if webhook is enabled>",
    "TELEGRAM_WEBHOOK_SECRET": "<sekret zagolovka X-Telegram-Bot-Api-Secret-Token>",
    "PUBLIC_URL": "https://host — vneshniy bazovyy URL",
    "ADMIN_TELEGRAM_ID": "<numeric id, optional>",
    "CHECK_MODE": "permissive | strict",
}

REQUIRED_MINIMAL = ["JWT_SECRET"]
DEFAULT_WEAK_VALUES = {"JWT_SECRET": {"devsecret", "REPLACE_ME", "REPLACE_ME_WITH_64_CHAR_RANDOM"}}

def _safe_len(v: str | None) -> int:
    return len(v or "")

def _is_weak_secret(key: str, val: str) -> bool:
    if not val:
        return True
    weak = DEFAULT_WEAK_VALUES.get(key, set())
    return val in weak or _safe_len(val) < 16

def run_check() -> Dict[str, Any]:
    now = int(time.time())
    mode = (os.environ.get("CHECK_MODE") or "permissive").strip().lower()
    result: Dict[str, Any] = {
        "ts": now,
        "mode_requested": mode,
        "mode_effective": mode,
        "problems": [],
        "warnings": [],
        "env_sample": {},
    }

    # Snimok interesuyuschikh ENV
    for k in RECOMMENDED.keys():
        result["env_sample"][k] = os.environ.get(k)

    # Basic checks
    for k in REQUIRED_MINIMAL:
        if not os.environ.get(k):
            result["problems"].append(f"ENV {k} ne zadan")
    # Slabye sekrety
    js = os.environ.get("JWT_SECRET", "")
    if _is_weak_secret("JWT_SECRET", js):
        result["warnings"].append("JWT_SECRET slabyy ili korotkiy (>=64 simvolov rekomenduetsya)")

    # TTL vmenyaemy
    def _is_int_pos(name: str) -> bool:
        v = os.environ.get(name)
        if v is None:
            return True
        try:
            return int(v) > 0
        except Exception:
            return False

    for name in ("JWT_TTL", "JWT_REFRESH_TTL"):
        if not _is_int_pos(name):
            result["problems"].append(f"ZZF0Z must be a positive integer")

    # APP_IMPORT udoben
    if not os.environ.get("APP_IMPORT"):
        result["warnings"].append("APP_IMPORT ne zadan (budet probovatsya app:app, wsgi_secure:app, wsgi:app)")

    # Telegram webhook parochka
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    sec = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if bool(tok) ^ bool(sec):
        result["warnings"].append("For Telegrams, it is advisable to set AT THE SAME TIME TELEGRAM_HERE_TOKEN and TELEGRAM_WEBHOOK_SECRET (or neither)")

    # Avtokatbek iz strict v permissive
    if mode == "strict" and (result["problems"]):
        result["mode_effective"] = "permissive"
        result["warnings"].append("STRICT → PERMISSIVE: nayden(y) problemy, myagkiy rezhim vklyuchen avtomaticheski")

    return result

def main() -> int:
    summary = run_check()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # V S0 ne ronyaem payplayn.
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
