# -*- coding: utf-8 -*-
"""scripts/ester_thinking_check.py

Legkiy self-check kaskadnogo myshleniya i voli Ester.

Mosty:
- Yavnyy: (CLI ↔ thinking_manifest) — daet bystryy otchet i status.
- Skrytyy #1: (modules.thinking.* ↔ engineer) — proveryaet nalichie klyuchevykh moduley.
- Skrytyy #2: (HTTP /ester/thinking/once ↔ CLI) - optionalno pinguet HTTP-vkhod.

ENV:
    ESTER_THINK_CHECK_AB = "A" | "B"
    A - tolko lokalnye proverki moduley.
    B - dopolnitelno try HTTP-zapros k /ester/thinking/ping (esli server uzhe zapuschen).

Zemnoy abzats:
Inzhener zapuskaet `python -m scripts.ester_thinking_check` i see:
chto imenno dostupno, kakie rezhimy vklyucheny i ne rushitsya li kaskad.
# c=a+b"""
from __future__ import annotations

import os
import sys
import json
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester.thinking_manifest import build_manifest, human_report
except Exception as e:  # pragma: no cover
    sys.stderr.write(f"[ester_thinking_check] import error: {e}\n")
    raise SystemExit(1)


def _http_ping() -> Any:
    import urllib.request
    import urllib.error

    url = os.getenv("ESTER_THINK_HTTP_PING", "http://127.0.0.1:8080/ester/thinking/ping")
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:  # nosec B310
            data = resp.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(data)
            except Exception:
                return {"raw": data}
    except urllib.error.URLError as e:
        return {"error": str(e)}


def main() -> int:
    m = build_manifest()
    print("[Ester thinking manifest]")
    print(json.dumps(m, ensure_ascii=False, indent=2))
    print()
    print(human_report())

    if (os.getenv("ESTER_THINK_CHECK_AB", "A") or "A").upper() == "B":
        print()
        print("[HTTP ping: /ester/thinking/ping]")
        res = _http_ping()
        print(json.dumps(res, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())