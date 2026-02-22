# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.reports.summary — svodnyy otchet (markdown).
Mosty:
- Yavnyy: build_summary() iz istochnikov → markdown cherez render_markdown().
- Skrytyy #1: (DX ↔ Publikatsiya) — legkiy generator bez vneshnikh paketov.
- Skrytyy #2: (Kachestvo ↔ Prozrachnost) — otchet daet konsolidirovannyy vzglyad dlya priemki.

Zemnoy abzats:
Prostoy tekstovyy otchet — kak «kardiogramma»: bystro ponyat zhiv li patsient i gde anomalii.
# c=a+b
"""
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def build_summary(sources: Dict[str, Any]) -> Dict[str, Any]:
    # Prosteyshie agregatsii
    out = {
        "ok": True,
        "counts": {},
        "notes": [],
    }
    for k, v in sources.items():
        if isinstance(v, list):
            out["counts"][k] = len(v)
        elif isinstance(v, dict):
            out["counts"][k] = len(v)
        else:
            out["counts"][k] = 1 if v else 0
    return out

def render_markdown(summary: Dict[str, Any], title: str="Ester Report") -> str:
    lines: List[str] = [f"# {title}", "", "## Counters"]
    for k, c in summary.get("counts", {}).items():
        lines.append(f"- **{k}**: {c}")
    if summary.get("notes"):
        lines.append("")
        lines.append("## Notes")
        for n in summary["notes"]:
            lines.append(f"- {n}")
    lines.append("")
    lines.append("_c=a+b_")
    return "\n".join(lines)