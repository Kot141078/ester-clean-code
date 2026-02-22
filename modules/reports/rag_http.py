
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.reports.rag_http — markdown‑svodka po RAG indeksu.
Rout: `/compat/reports/rag.md` (FastAPI/Flask, ruchnoe podklyuchenie).
# c=a+b
"""
import os
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")

def _md() -> str:
    from modules.rag import hub
    st = hub.status()
    items = hub.search("the", k=5).get("items", []) if st.get("docs",0) else []
    lines = [
        "# Ester — RAG Report",
        "",
        "## Status",
        f"- docs: {st.get('docs')}",
        f"- ab: {st.get('ab')}",
        f"- dim: {st.get('dim')}",
        f"- adaptive: {st.get('adaptive', False)}",
        "",
        "## Top examples",
    ]
    for it in items:
        lines.append(f"- ({it.get('score',0):.3f}) #{it.get('id')}: {it.get('text')[:80]}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/rag.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/rag.md")
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    return True