# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.reports.metrics_http — markdown-metriki kachestva.
Rout: `/compat/reports/metrics.md` (FastAPI/Flask).
# c=a+b
"""
import os
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")

def _md() -> str:
    from modules.quality import guard
    st = guard.status()
    lines = [
        "# Ester — Quality Metrics",
        "",
        "## Window / Config",
        f"- window_sec: {st.get('config',{}).get('window_sec')}",
        f"- p90_target_ms: {st.get('config',{}).get('p90_ms')}",
        f"- error_threshold: {st.get('config',{}).get('error_rate')}",
        "",
        "## Observed (current window)",
        f"- samples: {st.get('recent_count')}",
        f"- p90_ms_observed: {st.get('p90_ms_observed')}",
        f"- error_rate_observed: {st.get('error_rate_observed')}",
        "",
        "## Decision",
        f"- last_decision: {st.get('last_decision')}",
        "",
        "_c=a+b_",
    ]
    return "\n".join(lines)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/metrics.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/metrics.md")
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    return True