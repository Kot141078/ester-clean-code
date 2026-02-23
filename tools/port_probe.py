#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S0/tools/port_probe.py — Bystraya proverka dostupnosti BASE_URL na urovne TCP/TLS + GET /live.

Mosty:
- Yavnyy: Enderton (logika) — proverka formalizuetsya kak predikaty: TCP dostupen ∧ (opts.) TLS rukopozhatie prokhodit.
- Skrytyy #1: Ashbi (kibernetika) — regulyator prosche sistemy: minimalnyy TCP dial + prostoy GET dostatochno dlya pervichnoy diagnostiki.
- Skrytyy #2: Cover & Thomas (infoteoriya) — snimaem neopredelennost: otlichaem «port zakryt», «TLS ne soshelsya», «HTTP zhiv».

Zemnoy abzats (inzheneriya):
Skript ne trogaet rantaym. Delaet TCP-konnekt k khost:port, pytaetsya TLS (esli skhema https),
posle — GET /live s taymautom. Vse na standartnoy biblioteke. Vydaet JSON-itog.

# c=a+b
"""
from __future__ import annotations
import json
import os
import socket
import ssl
import sys
from urllib.parse import urlparse
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
TIMEOUT = float(os.environ.get("PORT_PROBE_TIMEOUT", "3.0"))

def _tcp_check(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True
    except Exception:
        return False

def _tls_check(host: str, port: int) -> bool:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host):
                return True
    except Exception:
        return False

def _http_get(url: str) -> int | None:
    try:
        with request.urlopen(url, timeout=TIMEOUT) as resp:
            return resp.status
    except error.HTTPError as e:
        return e.code
    except Exception:
        return None

def main() -> int:
    u = urlparse(BASE_URL)
    scheme = (u.scheme or "http").lower()
    host = u.hostname or "127.0.0.1"
    port = u.port or (443 if scheme == "https" else 80)

    tcp_ok = _tcp_check(host, port)
    tls_ok = None
    if scheme == "https":
        tls_ok = _tls_check(host, port)

    live_status = _http_get(BASE_URL.rstrip("/") + "/live") if tcp_ok else None

    out = {
        "base_url": BASE_URL,
        "tcp_ok": tcp_ok,
        "tls_ok": tls_ok,
        "live_status": live_status,
        "timeout_s": TIMEOUT,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())