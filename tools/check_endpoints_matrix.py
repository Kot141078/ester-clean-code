#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tools/check_endpoints_matrix.py - Matritsa statusov endpointov (s/bez JWT) v Markdown.

Mosty:
- Yavnyy: Dzheynes (bayes) - statusy kodov eto “nablyudeniya”, povyshayuschie/ponizhayuschie pravdopodobie gipotezy “sistema zdorova”.
- Skrytyy #1: Enderton (logika) - matritsa = kompozitsiya predikatov (metod, put, zagolovki), proveryaemaya bez izmeneniya koda.
- Skrytyy #2: Ashbi (kibernetika) — A/B-slot: A=myagkiy (net tokena → net padeniy), B=strogiy (trebuet JWT), s avtokatbekom.

Zemnoy abzats (inzheneriya):
Instrument chitaet spisok putey (po umolchaniyu iz tests/fixtures/endpoints.txt),
khodit GET k kazhdomu v dvukh rezhimakh: bez tokena i s tokenom. Token beretsya iz ENV JWT_TOKEN,
ili generiruetsya cherez tools/jwt_mint.py pri nalichii JWT_SECRET. Dlya webhook add sekretnyy zagolovok.
Vykhod - Markdown-tablitsa, sokhranyaemaya v --out ili pechataemaya v stdout.

# c=a+b"""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
from typing import List, Tuple
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
TIMEOUT = float(os.environ.get("HTTP_SMOKE_TIMEOUT", "3.0"))

DEFAULT_ENDPOINTS_FILE = "tests/fixtures/endpoints.txt"

def _http_get(path: str, headers: dict | None = None) -> Tuple[int | None, str]:
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
        return None, f"ERR: {e}"

def _mint_jwt_fallback(name: str = "Owner", role: str = "admin", ttl: int = 600) -> str | None:
    # 1) ENV JWT_TOKEN
    tok = os.environ.get("JWT_TOKEN")
    if tok:
        return tok.strip()

    # 2) Let's try to call tools/zhvt_mint.po (if available) from ENV ZhVT_SEKRET
    if os.path.isfile("tools/jwt_mint.py") and os.environ.get("JWT_SECRET"):
        try:
            token = subprocess.check_output(
                ["python", "tools/jwt_mint.py", "--user", name, "--role", role, "--ttl", str(ttl)],
                text=True,
            ).strip()
            return token
        except Exception:
            pass

    # 3) Net tokena
    return None

def _read_endpoints(path: str) -> List[str]:
    if not os.path.isfile(path):
        # defoltnyy nabor
        return ["/live", "/ready", "/admin", "/portal", "/api/telegram/webhook"]
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(s)
    return lines

def _render_md(rows: List[Tuple[str, str, str]]) -> str:
    # rows: [(path, no_jwt, with_jwt)]
    out = []
    out.append(f"# Endpoint matrix — BASE_URL={BASE_URL}\n")
    out.append("| Path | No JWT | With JWT |")
    out.append("|------|--------|----------|")
    for p, a, b in rows:
        out.append(f"| `{p}` | {a} | {b} |")
    out.append("")
    return "\n".join(out)

def main() -> int:
    ap = argparse.ArgumentParser(description="Matritsa statusov endpointov")
    ap.add_argument("--endpoints", default=DEFAULT_ENDPOINTS_FILE, help="Fayl so spiskom putey (po odnomu na stroku)")
    ap.add_argument("--out", default="-", help="File Markdovn or ь for stdout")
    args = ap.parse_args()

    endpoints = _read_endpoints(args.endpoints)
    token = _mint_jwt_fallback()
    rows: List[Tuple[str, str, str]] = []

    for path in endpoints:
        # Bez JWT
        code_a, _ = _http_get(path)
        cell_a = f"`{code_a}`" if code_a is not None else "`-`"

        # With gastrointestinal tract (if any)
        hdrs = {}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"

        # Osobyy sluchay: webhook sekret
        if path.endswith("/api/telegram/webhook") and os.environ.get("TELEGRAM_WEBHOOK_SECRET"):
            # For GET this is not critical, but add the header to pass basic checks
            hdrs["X-Telegram-Bot-Api-Secret-Token"] = os.environ["TELEGRAM_WEBHOOK_SECRET"]

        code_b, _ = _http_get(path, headers=hdrs if token or hdrs else None)
        cell_b = f"`{code_b}`" if code_b is not None else "`-`"
        rows.append((path, cell_a, cell_b))

    md = _render_md(rows)
    if args.out != "-":
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"legal_endpoints_matrix Report recorded in ZZF0Z")
        except Exception as e:
            print(f"yuchesk_endpoints_matrixsch VARN: failed to write file (ZZF0Z). I am typing in stdout.")
            print(md)
    else:
        print(md)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())