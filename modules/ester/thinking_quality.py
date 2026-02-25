# -*- coding: utf-8 -*-
"""modules/ester/thinking_quality.py

Otsenka "chelovechnosti" kaskadnogo myshleniya Ester poverkh suschestvuyuschego treys-adaptera.

Mosty:
- Yavnyy: (modules.thinking.thought_trace_adapter <-> inzhener) — prevraschaet treys kaskada v metriki kachestva.
- Skrytyy #1: (ester_thinking_check / ester_thinking_mode <-> quality) — daet chislovoy otvet, naskolko rezhim blizok k chelovecheskomu.
- Skrytyy #2: (HTTP /ester/thinking/once <-> offline-analiz) - odni i te zhe kriterii dlya CLI i HTTP.

Zemnoy abzats:
Inzheneru nuzhen bystryy otvet: eto byl "zhivoy" kaskad s obdumyvaniem,
ili ploskiy prokhod po payplaynu. Modul daet chislovoy skor i binarnyy flag human_like,
osnovannyy na glubine, vetvlenii, refleksii i obraschenii k pamyati.
# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.thinking import thought_trace_adapter as _tta
except Exception:  # pragma: no cover
    _tta = None  # type: ignore


def _as_bool(val: Any, default: bool) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _merge_variants_meta(cascade_result: Dict[str, Any], base_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Popytka "dochitat" glubinu i slozhnost iz multi-variants (ethics/science/engineering),
    kotorye formiruyutsya always_thinker dlya human_like-rezhima.

    Rabotaet tolko kogda bazovyy treys vyglyadit ploskim (depth ~0, bez vetvleniya/refleksii),
    chtoby ne lomat normalnye odinochnye kaskady."""
    try:
        if (
            base_meta.get("depth", 0.0) >= 1.0
            or base_meta.get("has_branch")
            or base_meta.get("has_reflect")
        ):
            return base_meta

        raw = cascade_result.get("raw") or cascade_result.get("result", {}).get("raw")
        if not isinstance(raw, dict):
            return base_meta
        variants = raw.get("variants")
        if not isinstance(variants, list) or not variants:
            return base_meta
    except Exception:
        return base_meta

    depths = []
    complexities = []
    refl_flags = []

    for v in variants:
        if not isinstance(v, dict):
            continue
        profile = v.get("profile") or {}
        if not isinstance(profile, dict):
            continue

        stages = profile.get("stages") or []
        steps_count = profile.get("steps_count") or 0
        complexity_score = (
            profile.get("complexity_score")
            or profile.get("complexity")
            or 0.0
        )

        if stages:
            try:
                depths.append(float(len(stages)))
            except Exception:
                pass
            refl_flags.append("reflect" in stages)
        elif steps_count:
            try:
                depths.append(float(steps_count))
            except Exception:
                pass

        try:
            complexities.append(float(complexity_score))
        except Exception:
            pass

    if not depths and not complexities:
        return base_meta

    new_meta = dict(base_meta)
    if depths:
        new_meta["depth"] = max(float(base_meta.get("depth", 0.0)), max(depths))
    if complexities:
        new_meta["complexity"] = max(float(base_meta.get("complexity", 0.0)), max(complexities))
    if refl_flags:
        new_meta["has_reflect"] = bool(base_meta.get("has_reflect") or any(refl_flags))

    # the presence of several options is interpreted as branching points of view
    try:
        br_cnt = int(len(variants))
    except Exception:
        br_cnt = 0
    new_meta["branch_count"] = max(int(base_meta.get("branch_count", 0)), br_cnt)
    new_meta["has_branch"] = bool(new_meta["branch_count"] > 0)

    return new_meta


def analyze_cascade(cascade_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Postroit metriki kachestva kaskada.

    Vozvraschaet:
        {
          "ok": bool,
          "meta": {...},     # metadannye iz trace_adapter/variants
          "score": float,    # 0..1
          "human_like": bool,
          "reason": str,
        }
    """
    if not isinstance(cascade_result, dict):
        return {
            "ok": False,
            "score": 0.0,
            "human_like": False,
            "reason": "cascade_result is not a dict",
        }

    if _tta is None:
        # Without an adapter, it cannot deeply evaluate, but does not break.
        return {
            "ok": True,
            "score": 0.0,
            "human_like": False,
            "reason": "thought_trace_adapter nedostupen; vklyuchite ESTER_TRACE_AB=B i adapter.",
        }

    tr = _tta.from_cascade_result(cascade_result)
    if not tr.get("ok"):
        return {
            "ok": False,
            "score": 0.0,
            "human_like": False,
            "reason": "trace_adapter ne smog razobrat rezultat kaskada",
        }

    info = tr.get("info") or {}

    # Bazovye priznaki iz trace_adapter
    base_meta = {
        "depth": float(info.get("depth") or 0.0),
        "branch_count": int(info.get("branch_count") or 0),
        "recall_count": int(info.get("recall_count") or 0),
        "has_reflect": bool(info.get("has_reflect") or False),
        "has_recall": bool(info.get("has_recall") or (info.get("recall_count") or 0) > 0),
        "has_branch": bool(info.get("has_branch") or (info.get("branch_count") or 0) > 0),
        "complexity": float(info.get("complexity") or 0.0),
    }

    # If this is a multi-variant of human_like (ethniss/scene/engineering), we further enrich the meta.
    meta = _merge_variants_meta(cascade_result, base_meta)

    depth = float(meta.get("depth") or 0.0)
    branch_cnt = int(meta.get("branch_count") or 0)
    recall_cnt = int(meta.get("recall_count") or 0)
    has_reflect = bool(meta.get("has_reflect") or False)
    has_recall = bool(meta.get("has_recall") or (recall_cnt > 0))
    has_branch = bool(meta.get("has_branch") or (branch_cnt > 0))
    complexity = float(meta.get("complexity") or 0.0)

    # Threshold values ​​(soft), can be configured via ENV
    min_depth = float(os.getenv("ESTER_THINK_MIN_DEPTH", "4"))
    min_complexity = float(os.getenv("ESTER_THINK_MIN_COMPLEXITY", "3.5"))
    min_branch = int(os.getenv("ESTER_THINK_MIN_BRANCHES", "1"))
    require_reflect = _as_bool(os.getenv("ESTER_THINK_REQUIRE_REFLECT", "1"), True)
    require_recall = _as_bool(os.getenv("ESTER_THINK_REQUIRE_RECALL", "0"), False)

    # Skor: vzveshennaya summa priznakov (0..1, grubo)
    score_parts = []

    # Glubina
    score_parts.append(min(depth / max(min_depth, 1.0), 1.0))
    # Vetvlenie
    if min_branch > 0:
        score_parts.append(min(branch_cnt / float(min_branch), 1.0))
    else:
        score_parts.append(1.0)
    # Slozhnost
    score_parts.append(min(complexity / max(min_complexity, 0.1), 1.0))
    # Refleksiya
    score_parts.append(1.0 if has_reflect else 0.0)
    # Memory (if required)
    if require_recall:
        score_parts.append(1.0 if has_recall else 0.0)

    score = sum(score_parts) / float(len(score_parts) or 1)

    # Usloviya human_like
    human_like = True
    reasons = []

    if depth < min_depth:
        human_like = False
        reasons.append(f"glubina {depth:.1f} < {min_depth}")
    if branch_cnt < min_branch:
        human_like = False
        reasons.append(f"vetvleniy {branch_cnt} < {min_branch}")
    if complexity < min_complexity:
        human_like = False
        reasons.append(f"complexity {complexity:.2f} < {min_complexity}")
    if require_reflect and not has_reflect:
        human_like = False
        reasons.append("net refleksii")
    if require_recall and not has_recall:
        human_like = False
        reasons.append("no memory accesses")

    if not reasons:
        reasons.append("the cascade meets the target criteria human_like")

    return {
        "ok": True,
        "meta": {
            "depth": depth,
            "branch_count": branch_cnt,
            "recall_count": recall_cnt,
            "has_reflect": has_reflect,
            "has_recall": has_recall,
            "has_branch": has_branch,
            "complexity": complexity,
        },
        "score": round(float(score), 3),
        "human_like": bool(human_like),
        "reason": "; ".join(reasons),
    }