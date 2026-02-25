#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/p2p_sign.py — generator zagolovkov P2P-podpisi.

Mosty:
- Yavnyy: (CLI ↔ Server) khedery 100% sootvetstvuyut proverke v security/p2p_signature.verify/verify_any.
- Skrytyy #1: (Dev UX ↔ CI) vyvod srazu v format -H "K: V" dlya udobnoy skleyki s curl/smoke.
- Skrytyy #2: (Legacy ↔ New) --legacy vklyuchaet X-P2P-Auth po uproschennoy formule bez lomki servernoy sovmestimosti.

Zemnoy abzats:
Odin skript pokryvaet i novyy, i staryy formaty - menshe sluchaynykh 401 i raznoboya mezhdu klientami.
# c=a+b"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys
import time
import typing as _t
from urllib.parse import urlparse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import typer  # type: ignore
except Exception:
    print("ERROR: 'typer' is required. Try: pip install typer", file=sys.stderr)
    sys.exit(2)

app = typer.Typer(help="Generate P2P signature headers for Ester.")

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _read_body(body_path: str | None) -> bytes:
    if not body_path or body_path == "-":
        # If stdin is not connected, read empty body
        if sys.stdin and not sys.stdin.isatty():
            return sys.stdin.buffer.read()
        return b""
    with open(body_path, "rb") as f:
        return f.read()

def _path_only(target: str) -> str:
    """Accepts either an absolute URL or a path like /self/archive - returns path."""
    if not target:
        return "/"
    if "://" in target:
        return urlparse(target).path or "/"
    return target if target.startswith("/") else "/" + target

def _sign_new(secret: str, ts: int, method: str, path: str, body: bytes) -> str:
    msg = f"{ts}\n{method.upper()}\n{path}\n{_sha256_hex(body)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def _sign_legacy(secret: str, ts: int, method: str, path: str) -> str:
    msg = f"{method.upper()}\n{path}\n{ts}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def sign(secret: str, ts: int, method: str, path: str, body: bytes) -> str:
    """Public helper used by tests/scripts."""
    return _sign_new(secret, int(ts), str(method), str(path), body)

def _print_headers(headers: dict[str, str], mode: str) -> None:
    """
    mode: 'curl' → -H 'K: V' na odnoy stroke; 'raw' → 'K: V' postrochno.
    """
    if mode == "raw":
        for k, v in headers.items():
            print(f"{k}: {v}")
        return
    # By default - one line with several -X, convenient for sargs
    parts = [f"-H '{k}: {v}'" for k, v in headers.items()]
    print(" ".join(parts))

@app.command()
def main(
    method: str = typer.Argument(..., help="HTTP method, e.g. GET/POST"),
    target: str = typer.Argument(..., help="Absolute URL or path, e.g. /self/archives"),
    body: str = typer.Option(None, "--body", "-b", help="Body file path or '-' for stdin"),
    secret: str = typer.Option(None, "--secret", "-s", help="Secret, overrides ESTER_P2P_SECRET"),
    ts: int = typer.Option(None, "--ts", help="Custom unix timestamp"),
    legacy: bool = typer.Option(False, "--legacy", help="Use legacy X-P2P-Auth instead of new X-P2P-Signature"),
    node: str = typer.Option(None, "--node", help="Optional node id for X-P2P-Node"),
    print_mode: str = typer.Option("curl", "--print", help="Output: curl|raw", show_default=True),
) -> None:
    """Primery:
      $ export ESTER_P2P_SECRET=dev-secret
      $ scripts/p2p_sign.py GET /self/archives
      $ scripts/p2p_sign.py POST http://127.0.0.1:8000/p2p/push -b payload.json
      $ scripts/p2p_sign.py --legacy GET /self/archives
      $ scripts/p2p_sign.py GET /self/archives --print raw"""
    secret_env = secret or os.getenv("ESTER_P2P_SECRET", "")
    if not secret_env:
        # Does not block: returns only S-P2P-Ts/S-P2P-Nodier, so that it is convenient to debug in non-wired environments
        typer.secho("WARNING: ESTER_P2P_SECRET is empty; printing minimal headers.", fg="yellow")

    method = (method or "GET").upper()
    path = _path_only(target)
    body_bytes = _read_body(body)
    when = int(ts or time.time())

    headers: dict[str, str] = {}
    headers["X-P2P-Ts"] = str(when)
    if node:
        headers["X-P2P-Node"] = node

    if secret_env:
        if legacy:
            headers["X-P2P-Auth"] = _sign_legacy(secret_env, when, method, path)
        else:
            headers["X-P2P-Signature"] = _sign_new(secret_env, when, method, path, body_bytes)

    _print_headers(headers, print_mode)

if __name__ == "__main__":
    app()
