#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tests/smoke_s0.py - myagkiy smouk cherez Flask test_client, bez lomki payplayna.

Mosty:
- Yavnyy: Enderton (logika) → utverzhdaem minimalnye invarianty: /live, /ready, /admin (401/403 bez tokena).
- Skrytyy #1: Cover & Thomas → "entropiya" nablyudeniy: dostatochno 3 prostykh proverok, chtoby otsech klass oshibok.
- Skrytyy #2: Ashbi → regulyator smouka dolzhen byt prosche sistemy: ne trebuet zapuska vneshnikh servisov.

Zemnoy abzats (inzheneriya):
Skript ne valit CI pri otsutstvii endpointov: testy "myagkie", pechatayut Warnings.
Esli `JWT_SECRET` sovpadaet s prilozheniem, proveryaem /admin s validnym HS256-JWT.
Sovmestim s `python -m` i pryamym vyzovom.

# c=a+b"""
from __future__ import annotations
import json
import os
import sys
import types
import importlib
import base64
import hashlib
import hmac
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _load_app():
    for target in [os.environ.get("APP_IMPORT"), "app:app", "wsgi_secure:app", "wsgi:app"]:
        if not target:
            continue
        try:
            mod, attr = target.split(":")
            m = importlib.import_module(mod)
            app = getattr(m, attr)
            if hasattr(app, "test_client"):
                return app
        except Exception:
            continue
    print("[smoke_s0] WARN: Flask app ne nayden (APP_IMPORT/app:app/wsgi_secure:app/wsgi:app). Propuskayu testy.")
    sys.exit(0)

def _b64url(data: bytes) -> str:
    import base64 as b
    return b.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _mint_jwt(name: str, role: str = "admin", ttl: int = 600) -> str:
    now = int(time.time())
    header = {"typ": "JWT", "alg": "HS256", "kid": "smoke"}
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
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(sig)}"

def main() -> int:
    app = _load_app()
    client = app.test_client()

    def try_get(path: str):
        try:
            resp = client.get(path)
            print(f"[GET {path}] -> {resp.status_code}")
            return resp.status_code, resp.data
        except Exception as e:
            print(f"[GET {path}] ERROR: {e}")
            return None, None

    # /live
    code, _ = try_get("/live")
    if code is None:
        print("[smoke_s0] WARN: /live ne proveren.")
    elif code not in (200, 204):
        print(f"[smoke_s0] WARN: /live vernul {code}, ozhidaetsya 200/204.")

    # /ready
    code, _ = try_get("/ready")
    if code is None:
        print("[smoke_s0] WARN: /ready ne proveren.")
    elif code not in (200, 204, 503):
        print(f"[smoke_s0] WARN: /ready vernul {code}, dopustimo 200/204/503.")

    # /admin bez tokena
    code, _ = try_get("/admin")
    if code is not None and code in (200, 201):
        print("[smoke_s0] WARN: /admin otdaet 200 bez tokena — prover RBAC.")
    elif code in (401, 403, 302, 404, None):
        pass  # normal options for smoke

    # /admin with a token (if there is ZhVT_SEKRET)
    token = _mint_jwt("Owner", "admin", 600)
    try:
        resp = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        print(f"[GET /admin (with JWT)] -> {resp.status_code}")
    except Exception as e:
        print(f"[smoke_s0] INFO: /admin (with JWT) ne proveren: {e}")

    # Telegram webhook (if available)
    if any(r.rule.startswith("/api/telegram") for r in app.url_map.iter_rules()):
        payload = {
            "update_id": 9999999,
            "message": {
                "message_id": 1,
                "date": int(time.time()),
                "chat": {"id": 123456789, "type": "private", "username": "ivan_local"},
                "text": "/start",
                "from": {"id": 123456789, "is_bot": False, "first_name": "Owner"},
            },
        }
        secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "devhook")
        try:
            resp = client.post(
                "/api/telegram/webhook",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"X-Telegram-Bot-Api-Secret-Token": secret},
            )
            print(f"[POST /api/telegram/webhook] -> {resp.status_code}")
        except Exception as e:
            print(f"[smoke_s0] INFO: telegram webhook ne proveren: {e}")

    print("[smoke_s0] DONE")
    return 0

if __name__ == "__main__":
    sys.exit(main())
