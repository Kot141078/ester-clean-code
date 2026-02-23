# -*- coding: utf-8 -*-
"""
scripts/ester_thinking_quality.py

CLI-instrument dlya otsenki kachestva kaskadnogo myshleniya Ester.

Mosty:
- Yavnyy: (cascade_closed / ester_thinking_http <-> thinking_quality) — edinye kriterii dlya lokalnogo i HTTP-rezhima.
- Skrytyy #1: (inzhener <-> metriki) — daet chislovoy skor i tekstovuyu prichinu.
- Skrytyy #2: (thinking_manifest <-> profili) — pomogaet proverit, chto profil human_like realno daet human_like-kasCADE.

Ispolzovanie:

1) Lokalnyy test kaskada (bez HTTP):

    python -m scripts.ester_thinking_quality

2) HTTP-test cherez /ester/thinking/once (esli app.py zapuschen i profil vystavlen):

    python -m scripts.ester_thinking_quality http

ENV:
    ESTER_THINK_QUALITY_URL  — URL dlya HTTP-rezhima (po umolchaniyu /ester/thinking/once)
    Porogi chitayutsya iz modules.ester.thinking_quality (ESTER_THINK_MIN_DEPTH i dr.)

Zemnoy abzats:
Komanda daet prostoy otvet:
"score=0.87, human_like=True, prichina=kasCADE sootvetstvuet kriteriyam".
Eto udobno dlya regressionnykh testov i kontrolya evolyutsii myshleniya Ester.
# c=a+b
"""
from __future__ import annotations

import json
import sys
import os
from typing import Any, Dict

try:
    from modules.thinking import cascade_closed
except Exception:
    cascade_closed = None  # type: ignore

from modules.ester.thinking_quality import analyze_cascade
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _run_local() -> Dict[str, Any]:
    if cascade_closed is None:
        return {"ok": False, "error": "modules.thinking.cascade_closed nedostupen"}
    res = cascade_closed.run_cascade("quality self-check: human_like probe")
    q = analyze_cascade(res)
    return {"ok": True, "mode": "local", "cascade": res, "quality": q}


def _run_http() -> Dict[str, Any]:
    import urllib.request
    import urllib.error

    url = os.getenv("ESTER_THINK_QUALITY_URL", "http://127.0.0.1:8080/ester/thinking/once")
    payload = {
        "goal": "quality self-check via http: human_like probe",
        "priority": "high",
        "trace": True,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            raw = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"http error: {e}"}

    try:
        parsed = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "invalid json from server", "raw": raw[:4000]}

    # result mozhet lezhat libo v korne, libo v result
    cascade_res = parsed.get("result") or parsed
    q = analyze_cascade(cascade_res)
    return {"ok": True, "mode": "http", "response": parsed, "quality": q}


def main() -> int:
    mode = "local"
    if len(sys.argv) > 1:
        mode = sys.argv[1].strip().lower()

    if mode in ("local",):
        out = _run_local()
    elif mode in ("http", "remote"):
        out = _run_http()
    else:
        print("Usage: python -m scripts.ester_thinking_quality [local|http]", file=sys.stderr)
        return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())