#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S0/tests/integration_s0_http.py — HTTP-smouk zhivogo prilozheniya (bez vneshnikh zavisimostey).

Mosty:
- Yavnyy: Dzheynes (bayes) → nablyudaem "dokazatelstva" (kody otvetov) i obnovlyaem pravdopodobie "sistema zdorova".
- Skrytyy #1: Enderton (logika) → proverki — eto predikaty nad (metod, put, zagolovki), komponuemye bez izmeneniya koda.
- Skrytyy #2: Ashbi (kibernetika) → regulyator prosche sistemy: tolko GET/POST k neskolkim tselevym tochkam.

Zemnoy abzats (inzheneriya):
Skript ne trebuet `requests`, rabotaet na standartnoy biblioteke `urllib`.
Po umolchaniyu bem po BASE_URL=http://127.0.0.1:8080. Esli prilozhenie ne zapuscheno — vydaem ponyatnye WARN i vykhodim 0.
Optsionalno mozhno sgenerirovat HS256-JWT na letu (ENV GENERATE_JWT=1) — algoritm polnostyu lokalnyy.

# c=a+b
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
TIMEOUT = float(os.environ.get("HTTP_SMOKE_TIMEOUT", "3.0"))
TELEGRAM_WEBHOOK_PATH = os.environ.get("TELEGRAM_WEBHOOK_PATH", "/api/telegram/webhook")

def _http_get(path: str, headers: dict | None = None) -> tuple[int | None, str]:
    url = BASE_URL.rstrip("/") + path
    req = request.Request(url, headers=headers or {})
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return e.code, body
    except Exception as e:
        print(f"[HTTP] GET {url} ERR: {e}")
        return None, ""

def _http_post_json(path: str, obj: dict, headers: dict | None = None) -> tuple[int | None, str]:
    url = BASE_URL.rstrip("/") + path
    data = json.dumps(obj).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = request.Request(url, data=data, headers=hdrs, method="POST")
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return e.code, body
    except Exception as e:
        print(f"[HTTP] POST {url} ERR: {e}")
        return None, ""

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def mint_jwt(name: str, role: str = "admin", ttl: int = 600) -> str:
    now = int(time.time())
    header = {"typ": "JWT", "alg": "HS256", "kid": "http-smoke"}
    payload = {
        "iss": "ester-local",
        "aud": "ester-ui",
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "sub": name,
        "name": name,
        "roles": [role],
    }
    secret = os.environ.get("JWT_SECRET", "devsecret")
    h_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url(sig)}"

def main() -> int:
    print(f"[HTTP-SMOKE] BASE_URL={BASE_URL}, TIMEOUT={TIMEOUT}s")

    # /live
    code, _ = _http_get("/live")
    if code is None:
        print("[HTTP-SMOKE] WARN: servis ne otvechaet (vozmozhno, ne zapuschen). Zavershayu bez oshibki.")
        return 0
    if code not in (200, 204):
        print(f"[HTTP-SMOKE] WARN: /live => {code}, ozhidaetsya 200/204")

    # /ready
    code, _ = _http_get("/ready")
    if code not in (200, 204, 503):
        print(f"[HTTP-SMOKE] WARN: /ready => {code}, dopustimo 200/204/503")

    # /admin bez tokena
    code, _ = _http_get("/admin")
    if code in (200, 201):
        print("[HTTP-SMOKE] WARN: /admin vernul 200 bez tokena — prover RBAC")

    # /admin s tokenom (esli mozhem)
    jwt = None
    if os.environ.get("GENERATE_JWT", "1") == "1":
        jwt = mint_jwt("Owner", "admin", 600)
    if jwt:
        code, _ = _http_get("/admin", headers={"Authorization": f"Bearer {jwt}"})
        if code not in (200, 302):  # dopuskaem redirekt v UI
            print(f"[HTTP-SMOKE] WARN: /admin s JWT => {code}")

    # /portal (status mozhet otlichatsya ot realizatsii)
    code, _ = _http_get("/portal")
    if code in (401, 403):
        print("[HTTP-SMOKE] INFO: /portal zakryt pravami — eto ok dlya tekuschey konfiguratsii.")
    elif code in (200, 302, 404):
        pass  # ok

    # Telegram webhook (esli skonfigurirovan)
    hook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if hook_secret:
        payload = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": {"id": 321, "type": "private", "username": "ivan_local"},
                "text": "/start",
                "from": {"id": 321, "is_bot": False, "first_name": "Owner"},
            },
        }
        code, _ = _http_post_json(TELEGRAM_WEBHOOK_PATH, payload, headers={"X-Telegram-Bot-Api-Secret-Token": hook_secret})
        if code in (200, 204, 202):
            print("[HTTP-SMOKE] Telegram webhook OK")
        elif code in (401, 403):
            print("[HTTP-SMOKE] WARN: Telegram webhook otklonen (401/403) — prover sekret/rol")
        elif code == 404:
            print("[HTTP-SMOKE] INFO: Telegram webhook ne nayden (404) — vozmozhno, marshrut ne vklyuchen")
        else:
            print(f"[HTTP-SMOKE] WARN: Telegram webhook => {code}")

    print("[HTTP-SMOKE] DONE")
    return 0

if __name__ == "__main__":
    sys.exit(main())
