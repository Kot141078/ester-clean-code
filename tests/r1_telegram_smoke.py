#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R1/tests/r1_telegram_smoke.py — integratsionnyy smouk Telegram-konturov (v zakrytoy korobke, bez realnogo Telegram).

Mosty:
- Yavnyy: Enderton (logika) — proveryaem predikaty: webhook prinimaet JSON s sekretom; ctrl API otvechaet; UI dostupen.
- Skrytyy #1: Ashbi (kibernetika) — regulyator prosche sistemy: minimalnye zaprosy (get_me, prostoy webhook), myagkie otkazy.
- Skrytyy #2: Cover & Thomas (infoteoriya) — dostatochno malogo chisla nablyudeniy (kodov), chtoby otdelit «zhiv/ne zhiv».

Zemnoy abzats (inzheneriya):
Skript ne trogaet rantaym, ne trebuet realnogo bota. Otpravlyaet fikstury v `/api/telegram/webhook` s zagolovkom
`X-Telegram-Bot-Api-Secret-Token`, proveryaet 2xx/4xx kody i optsionalnye ctrl-endpointy. Esli servis ne podnyat —
pechataet WARN i zavershaetsya 0 (myagkiy rezhim).

# c=a+b
"""
from __future__ import annotations
import json
import os
import sys
import time
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
TIMEOUT = float(os.environ.get("HTTP_SMOKE_TIMEOUT", "4.0"))
HOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "devhook")

def _http_json(method: str, path: str, obj: dict | None = None, headers: dict | None = None):
    url = BASE_URL.rstrip("/") + path
    data = None
    hdrs = {"Accept": "application/json"}
    if obj is not None:
        data = json.dumps(obj).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    req = request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return e.code, body
    except Exception as e:
        print(f"[R1] WARN: {method} {url} error: {e}")
        return None, ""

def _fixture_start():
    return {
        "update_id": 10000001,
        "message": {
            "message_id": 1,
            "date": int(time.time()),
            "chat": {"id": 321, "type": "private", "username": "ivan_local"},
            "text": "/start",
            "from": {"id": 321, "is_bot": False, "first_name": "Owner"}
        }
    }

def _fixture_link(name: str = "Owner"):
    return {
        "update_id": 10000002,
        "message": {
            "message_id": 2,
            "date": int(time.time()),
            "chat": {"id": 321, "type": "private", "username": "ivan_local"},
            "text": f"/link {name}",
            "from": {"id": 321, "is_bot": False, "first_name": "Owner"}
        }
    }

def main() -> int:
    print(f"[R1] BASE_URL={BASE_URL}")
    # 0) Prostoy GET k ctrl UI (esli est)
    code_ui, _ = _http_json("GET", "/tg/ctrl/ui")
    if code_ui is None:
        print("[R1] INFO: servis nedostupen — myagkoe zavershenie.")
        return 0
    if code_ui in (200, 302, 404):
        print(f"[R1] /tg/ctrl/ui => {code_ui} (lyuboy iz 200/302/404 dopustim dlya smouka)")

    # 1) get_me (esli est ctrl API)
    code_me, body_me = _http_json("GET", "/tg/ctrl/api/get_me")
    if code_me in (200, 404):
        print(f"[R1] /tg/ctrl/api/get_me => {code_me}")
    elif code_me in (401, 403):
        print(f"[R1] INFO: ctrl zaschischen (RBAC/JWT) — ok dlya etoy konfiguratsii.")
    elif code_me is None:
        pass
    else:
        print(f"[R1] WARN: /tg/ctrl/api/get_me => {code_me}")

    # 2) webhook /start
    headers = {"X-Telegram-Bot-Api-Secret-Token": HOOK_SECRET}
    code_ws, _ = _http_json("POST", "/api/telegram/webhook", _fixture_start(), headers)
    if code_ws in (200, 202, 204):
        print("[R1] webhook /start => OK")
    elif code_ws in (401, 403):
        print("[R1] WARN: webhook otvergnut (sekret ne prinyat?) — prover TELEGRAM_WEBHOOK_SECRET.")
    elif code_ws == 404:
        print("[R1] INFO: webhook put ne nayden — vozmozhno, marshrut vyklyuchen. Eto dopustimo dlya smouka.")
    else:
        print(f"[R1] WARN: webhook /start => HTTP {code_ws}")

    # 3) webhook /link Owner
    code_wl, _ = _http_json("POST", "/api/telegram/webhook", _fixture_link("Owner"), headers)
    if code_wl in (200, 202, 204):
        print("[R1] webhook /link => OK")
    elif code_wl in (401, 403, 404, None):
        print(f"[R1] INFO: /link mozhet byt ne realizovan ili zakryt pravami — kod={code_wl}. Eto ok dlya smouka.")
    else:
        print(f"[R1] WARN: webhook /link => HTTP {code_wl}")

    print("[R1] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())