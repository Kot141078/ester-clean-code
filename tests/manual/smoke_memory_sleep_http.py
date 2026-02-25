# -*- coding: utf-8 -*-
"""tests/manual/smoke_memory_sleep_http.py

Ruchnoy HTTP-smoke dlya sutochnogo tsikla pamyati.

Use:
  - ESTER_BASE_URL or BASE_URL (po umolchaniyu http://127.0.0.1:8080)

Route:
  - GET /memory/sleep/status
  - POST /memory/sleep/run_now

ZEMNOY ABZATs:
Eto kak podoyti k shkafu s avtomatami i nazhat knopku "Nochnoy tsikl":
esli otvet 200 i ok/ili ponyatnaya oshibka — provodka est."""
from __future__ import annotations

import json
import os
import sys
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _base_url() -> str:
    return (
        os.getenv("ESTER_BASE_URL")
        or os.getenv("BASE_URL")
        or "http://127.0.0.1:8080"
    ).rstrip("/")


def _req(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    url = _base_url() + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    print(f"[sleep-http] {method} {url}")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw
    except error.URLError as e:
        print(f"[sleep-http] ERR: {e}")
        return 0, str(e)


def main() -> int:
    base = _base_url()
    print(f"[sleep-http] BASE_URL={base}")

    code, out = _req("GET", "/memory/sleep/status")
    if code == 0:
        print("yusleep-httpsch VARN: the service is not responding, perhaps it is not running - I exit without an error.")
        return 0

    print(json.dumps(out, ensure_ascii=False, indent=2))

    code, out = _req("POST", "/memory/sleep/run_now", {})
    if code and isinstance(out, dict):
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(out)

    print("[sleep-http] DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())