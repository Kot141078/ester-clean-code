# -*- coding: utf-8 -*-
"""
modules/thinking/thought_trace_adapter.py — chelovekochitaemyy treys myshleniya Ester.

Mosty:
- Yavnyy: (cascade_closed / will_scheduler_adapter ↔ Memory/Log) —
  delaet iz syrykh struktur kaskada svyaznyy rasskaz o tom, kak Ester dumala.
- Skrytyy #1: (Kaskad ↔ Chelovek) — vydaet ponyatnyy cheloveku narrativ shagov Think→Recall→Branch→Plan→Act→Reflect.
- Skrytyy #2: (Kaskad / Volya ↔ Diagnostika) — pozvolyaet bystro uvidet, est li vetvlenie, refleksiya, konteksty.

A/B-slot:
    ESTER_TRACE_AB = "A" | "B"
    A — legkiy rezhim: kratkiy treys bez lishnikh detaley.
    B — rasshirennyy rezhim: bolee razvernutaya rasshifrovka.

Zemnoy abzats (inzhener):
    from modules.thinking import cascade_closed
    from modules.thinking import thought_trace_adapter as tta

    c = cascade_closed.run_cascade("proverit treys")
    trace = tta.from_cascade_result(c)
    print(trace["text"])
# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import store
except Exception:  # pragma: no cover
    store = None  # type: ignore

try:
    from modules.memory.events import record_event
except Exception:  # pragma: no cover
    def record_event(*args: Any, **kwargs: Any) -> None:  # type: ignore
        return

_TRACE_MODE = (os.environ.get("ESTER_TRACE_AB", "A") or "A").strip().upper()


def _extract_steps(cascade: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps = cascade.get("steps") or []
    return steps if isinstance(steps, list) else []


def _guess_goal(cascade: Dict[str, Any]) -> str:
    goal = cascade.get("goal") or ""
    if goal:
        return str(goal)
    inner = cascade.get("result") or {}
    if isinstance(inner, dict):
        g = inner.get("goal")
        if g:
            return str(g)
    return "(tsel ne opredelena)"


def _analyze(cascade: Dict[str, Any]) -> Dict[str, Any]:
    steps = _extract_steps(cascade)
    goal = _guess_goal(cascade)
    summary = cascade.get("summary") or ""

    stages = [s.get("stage") for s in steps if isinstance(s, dict)]
    has_branch = "branch" in stages
    has_reflect = "reflect" in stages
    has_recall = "recall" in stages

    branches: List[str] = []
    for s in steps:
        if s.get("stage") == "branch":
            for c in s.get("candidates") or []:
                branches.append(str(c))

    used_pipelines: List[str] = []
    for s in steps:
        if s.get("stage") == "plan":
            for st in s.get("steps") or []:
                if isinstance(st, dict) and st.get("op") == "pipeline":
                    name = st.get("name")
                    if name and name not in used_pipelines:
                        used_pipelines.append(str(name))

    recall_count = None
    for s in steps:
        if s.get("stage") == "recall":
            c = s.get("count")
            if isinstance(c, int):
                recall_count = c
                break

    depth = len(steps)
    branch_cnt = len(branches)
    complexity = 1.0
    complexity += min(depth, 10) * 0.3
    complexity += min(branch_cnt, 10) * 0.2
    if has_reflect:
        complexity += 0.5
    if has_branch and has_recall:
        complexity += 0.5

    if complexity < 3:
        quality = "shallow"
    elif complexity < 6:
        quality = "normal"
    else:
        quality = "rich"

    return {
        "goal": goal,
        "summary": summary,
        "stages": stages,
        "has_branch": has_branch,
        "has_reflect": has_reflect,
        "has_recall": has_recall,
        "branches": branches,
        "used_pipelines": used_pipelines,
        "recall_count": recall_count,
        "depth": depth,
        "branch_count": branch_cnt,
        "complexity": round(complexity, 2),
        "quality": quality,
    }


def _format_text(info: Dict[str, Any]) -> str:
    goal = info["goal"]
    summary = info["summary"] or "Kaskad zavershen."
    stages = info["stages"]
    parts: List[str] = []

    parts.append(f"Tsel: {goal}")
    parts.append(f"Itog: {summary}")

    path = " → ".join([s for s in stages if s]) or "net yavnogo kaskada"
    parts.append(f"Put kaskada: {path}")

    if info["has_recall"]:
        rc = info.get("recall_count")
        if rc is not None:
            parts.append(f"Ester obraschalas k pamyati: {rc} fragm.")
        else:
            parts.append("Ester obraschalas k pamyati.")
    else:
        parts.append("Bez yavnogo obrascheniya k pamyati.")

    if info["has_branch"]:
        if info["branches"]:
            if _TRACE_MODE == "B":
                btxt = "; ".join(info["branches"][:5])
                parts.append("Vetvlenie gipotez: " + btxt)
            else:
                parts.append("Byli rassmotreny alternativnye gipotezy.")
    else:
        parts.append("Bez realnogo vetvleniya — reshenie pryamolineyno.")

    if info["has_reflect"]:
        parts.append("Byla stadiya refleksii: Ester otsenila svoi shagi i itog.")
    else:
        parts.append("Refleksiya minimalna — mozhno initsiirovat dopolnitelnoe osmyslenie.")

    if _TRACE_MODE == "B":
        parts.append(f"Slozhnost myshleniya: {info['complexity']} ({info['quality']}).")
        if info["used_pipelines"]:
            parts.append("Zadeystvovany payplayny: " + ", ".join(info["used_pipelines"]))

    return "\n".join(parts)


def from_cascade_result(cascade: Dict[str, Any]) -> Dict[str, Any]:
    """Postroit chelovekochitaemyy treys po rezultatu kaskada ili planirovschika."""
    if not isinstance(cascade, dict):
        return {"ok": False, "error": "expected dict"}

    base = cascade
    if "raw" in cascade and isinstance(cascade["raw"], dict):
        base = cascade["raw"]

    info = _analyze(base)
    text = _format_text(info)

    try:
        if store is not None and hasattr(store, "add_record"):
            memory_add(
                "think_trace",
                f"trace: {info['goal']}",
                {
                    "quality": info["quality"],
                    "complexity": info["complexity"],
                    "summary": info["summary"],
                },
            )
        record_event("think", "trace", True, {"goal": info["goal"], "q": info["quality"]})
    except Exception:
        pass

    return {"ok": True, "info": info, "text": text}