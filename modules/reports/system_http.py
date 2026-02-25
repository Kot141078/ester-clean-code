
# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.reports.system_http - system.md svodka (podklyuchenie vruchnuyu).
Mosty:
- Yavnyy: register_fastapi/register_flask pod prefiksom `/compat/reports` (ENV `ESTER_REPORTS_PREFIX`), url `/system.md`.
- Skrytyy #1: (Potoki ↔ Prozrachnost) - berem dannye iz media.watchers / media.progress.
- Skrytyy #2: (DX ↔ Integratsii) - markdown‑otvet, udobno dlya renderinga pryamo v brauzere.

Zemnoy abzats:
Kak itogovoe obsledovanie: dykhanie (potoki), pulse (schetchiki), temperatura (poslednie sobytiya) - v odnom fayle.
# c=a+b"""
import os
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")

def _md() -> str:
    from modules.media import watchers, progress
    dirs = watchers.get_dirs()
    sm = progress.summary()
    lines = [
        "# Ester — System",
        "",
        "## Folders",
        f"- in: `{dirs['in']}`",
        f"- out: `{dirs['out']}`",
        f"- tmp: `{dirs['tmp']}`",
        "",
        "## Progress",
    ]
    for k, v in sm.get("counters", {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Last events")
    for ev in sm.get("last", []):
        lines.append(f"- {ev.get('ts')}: {ev.get('status')} — {ev.get('src')}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/system.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/system.md")
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    return True