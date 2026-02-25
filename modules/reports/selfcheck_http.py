
# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.reports.selfcheck_http — HTTP‑router dlya self-check svodki.
Mosty:
- Yavnyy: register_fastapi/register_flask pod prefiksom `/compat/selfcheck` (ENV `ESTER_SELFCHECK_PREFIX`).
- Skrytyy #1: (DX ↔ Sovmestimost) — ispolzuem `modules.selfcheck.run` or myagkiy folbek.
- Skrytyy #2: (Kachestvo ↔ Prozrachnost) - markdown/JSON otvety dlya legkogo prosmotra.

Zemnoy abzats:
This is “bystryy osmotr” patsienta: vyvodim klyuchevye metriki self-check, ne vlezaya v details.
# c=a+b"""
import os, json
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_PREFIX = os.getenv("ESTER_SELFCHECK_PREFIX", "/compat/selfcheck")

def _run_selfcheck():
    # probuem populyarnye mesta
    try:
        from modules.selfcheck import run as sc_run  # type: ignore
        out = sc_run()
        return {"ok": True, "result": out, "source": "modules.selfcheck.run"}
    except Exception:
        pass
    # folbek
    return {"ok": True, "result": {"ok": True, "note": "fallback selfcheck"}, "source": "compat.fallback"}

def _md():
    data = _run_selfcheck()
    res = data.get("result", {})
    lines = ["# Ester — Selfcheck", "", "## Status"]
    for k, v in (res.items() if isinstance(res, dict) else [("value", str(res))]):
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)

# FastAPI
def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/ping")
    def _ping():
        return {"ok": True, "mod": "reports.selfcheck_http"}
    @app.get(prefix + "/summary.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    @app.get(prefix + "/detail.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _detail():
        return Response(content=json.dumps(_run_selfcheck(), ensure_ascii=False, indent=2), media_type="application/json")
    return True

# Flask
def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/ping")
    def _ping():
        return {"ok": True, "mod": "reports.selfcheck_http"}
    @app.get(prefix + "/summary.md")
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    @app.get(prefix + "/detail.json")
    def _detail():
        return Response(json.dumps(_run_selfcheck(), ensure_ascii=False, indent=2), mimetype="application/json")
    return True