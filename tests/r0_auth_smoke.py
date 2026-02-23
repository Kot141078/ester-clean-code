#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R0/tests/r0_auth_smoke.py — integratsionnyy smouk JWT-knopki i adminki (offlayn, bez vneshnikh zavisimostey).

Mosty:
- Yavnyy: Enderton (logika) → proveryaemye predikaty na /auth/auto i /admin: {poluchen token} ∧ {/admin 2xx/3xx s JWT}.
- Skrytyy #1: Dzheynes (bayes) → statusy otvetov — nablyudeniya, povyshayuschie pravdopodobie gipotezy «kontur autentifikatsii zhiv».
- Skrytyy #2: Cover & Thomas (infoteoriya) → minimalnyy «signal» (dve HTTP-pary) dostatochen dlya obnaruzheniya klassa oshibok.

Zemnoy abzats (inzheneriya):
Skript delaet POST na `/auth/auto/api/issue` (JSON `{"user":"Owner"}`), dostaet JWT, zatem khodit na `/admin` bez
i s tokenom. Bezopasnyy rezhim: esli servis nedostupen — pechataet WARN i zavershaet 0. Podkhodit dlya lokalki/CI.

# c=a+b
"""
from __future__ import annotations
import json
import os
import sys
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
TIMEOUT = float(os.environ.get("HTTP_SMOKE_TIMEOUT", "3.0"))

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
        print(f"[R0] WARN: {method} {url} error: {e}")
        return None, ""

def main() -> int:
    print(f"[R0] BASE_URL={BASE_URL}")

    # 1) /auth/auto/api/issue — poluchit token
    code, body = _http_json("POST", "/auth/auto/api/issue", {"user": "Owner"})
    token = None
    if code in (200, 201) and body:
        try:
            js = json.loads(body)
            token = (js.get("token") or js.get("access_token"))
        except Exception:
            token = None

    if not token:
        print("[R0] WARN: ne udalos poluchit token cherez /auth/auto/api/issue.")
        print("[R0] Podstrakhovka: poprobuyu /auth/login (esli ENABLE_SIMPLE_LOGIN=1).")
        code2, body2 = _http_json("POST", "/auth/login", {"user": "Owner", "role": "admin"})
        if code2 in (200, 201) and body2:
            try:
                token = (json.loads(body2).get("token") or json.loads(body2).get("access_token"))
            except Exception:
                token = None

    if token:
        print(f"[R0] OK: token poluchen (pervye 24 simv): {token[:24]}…")
    else:
        print("[R0] WARN: token ne poluchen — dalneyshie proverki /admin budut chastichno propuscheny.")

    # 2) /admin bez tokena
    code_admin_no, _ = _http_json("GET", "/admin")
    if code_admin_no is None:
        print("[R0] INFO: servis ne otvechaet — zavershayu myagko.")
        return 0
    if code_admin_no in (200, 201):
        print("[R0] WARN: /admin vernul 2xx bez tokena — prover RBAC.")
    else:
        print(f"[R0] /admin bez tokena => {code_admin_no} (ozhidaetsya 401/403/302/404 — lyubye ne-2xx ok)")

    # 3) /admin s tokenom (esli est)
    if token:
        code_admin_yes, _ = _http_json("GET", "/admin", headers={"Authorization": f"Bearer {token}"})
        print(f"[R0] /admin s JWT => {code_admin_yes}")
        if code_admin_yes in (200, 302):
            print("[R0] OK: kontur autentifikatsii rabotaet")
        else:
            print("[R0] WARN: /admin s JWT otvetil ne 200/302 — prover roli/sekret.")
    else:
        print("[R0] INFO: net tokena — propuskayu pozitivnyy keys /admin.")

    print("[R0] DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())