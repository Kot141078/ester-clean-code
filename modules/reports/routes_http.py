# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.reports.routes_http — markdown otchet po routam i kolliziyam.
Rout: `/compat/reports/routes.md` (FastAPI/Flask).
# c=a+b
"""
import os
from typing import Optional, Dict, List, Tuple
from collections import defaultdict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")

def _fastapi_dump(app) -> Dict[str, List[Tuple[str,str]]]:
    out = []
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", None) or getattr(r, "path_format", None)
        methods = getattr(r, "methods", None) or []
        for m in methods:
            out.append((str(m).upper(), str(path)))
    return _agg(out)

def _flask_dump(app) -> Dict[str, List[Tuple[str,str]]]:
    out = []
    url_map = getattr(app, "url_map", None)
    if url_map is not None:
        for r in url_map.iter_rules():
            methods = getattr(r, "methods", None) or []
            for m in methods:
                out.append((str(m).upper(), str(r.rule)))
    return _agg(out)

def _agg(pairs: List[Tuple[str,str]]) -> Dict[str, List[Tuple[str,str]]]:
    by = defaultdict(list)
    for m,p in pairs:
        by[f"{m} {p}"].append((m,p))
    return dict(by)

def _md_from_pairs(pairs: List[Tuple[str,str]]) -> str:
    # Gruppiruem i otmechaem dubli
    from collections import Counter
    cnt = Counter([f"{m} {p}" for m,p in pairs])
    lines = ["# Ester — Routes", ""]
    lines.append(f"**total:** {len(pairs)}")
    dups = [k for k,v in cnt.items() if v>1]
    lines.append(f"**collisions:** {len(dups)}")
    lines.append("")
    if dups:
        lines.append("## Collisions")
        for k in sorted(dups):
            lines.append(f"- {k} x{cnt[k]}")
        lines.append("")
    lines.append("## Sample")
    for k in sorted(list(cnt.keys()))[:40]:
        lines.append(f"- {k}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    def _md():
        pairs = []
        for r in getattr(app, "routes", []):
            path = getattr(r, "path", None) or getattr(r, "path_format", None)
            methods = getattr(r, "methods", None) or []
            for m in methods:
                pairs.append((str(m).upper(), str(path)))
        return _md_from_pairs(pairs)
    @app.get(prefix + "/routes.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _summary():
        return Response(content=_md(), media_type="text/markdown")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    def _md():
        pairs = []
        url_map = getattr(app, "url_map", None)
        if url_map is not None:
            for r in url_map.iter_rules():
                methods = getattr(r, "methods", None) or []
                for m in methods:
                    pairs.append((str(m).upper(), str(r.rule)))
        return _md_from_pairs(pairs)
    @app.get(prefix + "/routes.md")
    def _summary():
        return Response(_md(), mimetype="text/markdown")
    return True