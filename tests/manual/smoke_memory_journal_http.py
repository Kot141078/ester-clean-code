# -*- coding: utf-8 -*-
"""
tests/manual/smoke_memory_journal_http.py

Ruchnaya proverka HTTP-aliasa zhurnala pamyati.

Ispolzovanie:
  set BASE_URL=http://127.0.0.1:8080
  python tests/manual/smoke_memory_journal_http.py

Esli BASE_URL ne zadan, po umolchaniyu berem http://127.0.0.1:8080.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _base() -> str:
    return os.environ.get("BASE_URL") or "http://127.0.0.1:8080"


def _req(method: str, path: str, body: dict | None = None):
    url = _base().rstrip("/") + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            txt = resp.read().decode("utf-8")
            try:
                return resp.getcode(), json.loads(txt)
            except Exception:
                return resp.getcode(), {"raw": txt}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8")
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, {"raw": txt}
    except Exception as e:
        return 599, {"error": str(e)}


def main() -> int:
    print(f"[journal-http] BASE_URL={_base()}")
    code, data = _req("GET", "/memory/journal/ping")
    print("[journal-http] /memory/journal/ping =>", code, data)

    if not data.get("ok") and data.get("error"):
        print("[journal-http] WARN: alias reported error; check modules.memory.events and registration.")
        return 0

    code2, data2 = _req(
        "POST",
        "/memory/journal/event",
        {
            "kind": "smoke",
            "op": "manual_test",
            "ok": True,
            "info": {"from": "smoke_memory_journal_http"},
        },
    )
    print("[journal-http] /memory/journal/event =>", code2, data2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())