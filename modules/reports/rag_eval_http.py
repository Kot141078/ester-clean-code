# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.reports.rag_eval_http — offline RAG assessment report.
Path: e/comp/reports/rag_eval.mdjo.
# c=a+b"""
import os, json, time
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")
REPORT_JSON = os.path.join("data","rag_eval","last_report.json")
DATASET = os.path.join("data","rag_eval","demo.jsonl")

def _md() -> str:
    if not os.path.exists(REPORT_JSON):
        return "# RAG Eval\nthere is no report yet - run tools.verifiers_rag_eval\n\n_с=а+в_"
    with open(REPORT_JSON, "r", encoding="utf-8") as f:
        R = json.load(f)
    lines = ["# Ester — RAG Eval", ""]
    lines.append(f"- **n:** {R.get('n',0)}; **k:** {R.get('k',3)}")
    lines.append(f"- **hit@k:** {R.get('hit@k',0):.3f}")
    lines.append(f"- **coverage:** {R.get('cov',0):.3f}")
    lines.append(f"- **jaccard:** {R.get('jac',0):.3f}")
    lines.append("")
    rows = R.get("rows") or []
    if rows:
        lines.append("## Primery (poslednie)")
        for r in rows:
            lines.append(f"- Q: {r.get('q','')[:120]}")
            lines.append(f"  - hit={r.get('hit',0)}, cov={r.get('cov',0)}, jac={r.get('jac',0)}")
            ans = (r.get('ans','') or '').replace('\n',' ')[:200]
            lines.append(f"  - A: {ans}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    p = (prefix or _PREFIX) + "/rag_eval.md"
    @app.get(p, response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    p = (prefix or _PREFIX) + "/rag_eval.md"
    @app.get(p)
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    return True