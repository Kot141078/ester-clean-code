# -*- coding: utf-8 -*-
"""
tools/run_sleep_cycle_http.py — akkuratnyy HTTP-trigger nochnogo tsikla.

MOSTY:
- Yavnyy: (CLI/planirovschik ↔ /memory/sleep/*) — edinaya komanda zapuska sna.
- Skrytyy #1: (A/B ↔ ENV) — ispolzuet te zhe flagi, chto i manual-testy.
- Skrytyy #2: (operator ↔ stek pamyati) — vyvodit shagi i ikh ok/fail v chelovekochitaemom vide.

ZEMNOY ABZATs:
Inzhenerno: eto obertka vokrug suschestvuyuschego sleep API. Ee udobno veshat v planirovschik,
chtoby Ester regulyarno vypolnyala gigienu pamyati bez ruchnykh zapuskov testov.

# c=a+b
"""
from __future__ import annotations

import os
import sys
import json
from urllib import request, error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _base_url() -> str:
    return os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def _get(url: str) -> dict:
    try:
        with request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return json.loads(body)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _post(url: str) -> dict:
    req = request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return json.loads(body)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main(argv: list[str]) -> int:
    base = _base_url()
    status_url = base + "/memory/sleep/status"
    run_url = base + "/memory/sleep/run_now"

    st = _get(status_url)
    print("# status:")
    print(json.dumps(st, ensure_ascii=False, indent=2))

    res = _post(run_url)
    print("# run_now:")
    print(json.dumps(res, ensure_ascii=False, indent=2))

    return 0 if bool(res.get("ok", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))