# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.reports.rag_feedback_http - svodka RAG‑Feedback.
Rout: `/compat/reports/rag_feedback.md` (FastAPI/Flask).
# c=a+b"""
import os, json, time
from typing import Optional, List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")
DATA = os.path.join("data", "rag_feedback", "events.jsonl")

def _read_all(max_items: int = 200) -> List[Dict[str, Any]]:
    it: List[Dict[str, Any]] = []
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            for ln in f:
                ln = (ln or "").strip()
                if not ln: continue
                try:
                    it.append(json.loads(ln))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return it[-max_items:]

def _md() -> str:
    items = _read_all()
    lines = ["# Ester — RAG Feedback", ""]
    lines.append(f"**events:** {len(items)}")
    if not items:
        lines.append("empty for now")
        lines.append("")
        lines.append("_c=a+b_")
        return "\n".join(lines)
    # poslednie 10
    lines.append("")
    lines.append("## Poslednie")
    for ev in items[-10:]:
        q = (ev.get("q") or "")[:140].replace("\n"," ")
        t = (ev.get("text") or "")[:160].replace("\n"," ")
        lines.append(f"- **Q:** {q}")
        lines.append(f"  - A: {t}")
        srcs = ev.get("sources") or []
        if srcs:
            lines.append(f"  - sources: {min(3, len(srcs))}/{len(srcs)}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    p = (prefix or _PREFIX) + "/rag_feedback.md"
    @app.get(p, response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    p = (prefix or _PREFIX) + "/rag_feedback.md"
    @app.get(p)
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    return True