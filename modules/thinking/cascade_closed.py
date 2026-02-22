
# -*- coding: utf-8 -*-
"""
modules/thinking/cascade_closed.py — uluchshennoe kaskadnoe myshlenie (closed-box rezhim).

Goryachiy fiks:
- Isklyuchena zavisimost ot pipeline "decision_plan", chtoby ne triggerit
  bag v suschestvuyuschem vektornom poiske (raznye dliny vec).
- Ispolzuetsya lokalnoe bezopasnoe reshenie + pipeline "analyze_text".
- Nikakikh pravok modules/memory/*, tolko novyy modul.

Mosty:
- Yavnyy: (Kaskad ↔ Pipelines) — cherez bezopasnyy vyzov analyze_text.
- Skrytyy #1: (Memory ↔ Planirovanie) — store.query na etape Recall.
- Skrytyy #2: (Mysli ↔ Sobytiya) — record_event/record_thought po etapam kaskada.

A/B-slot:
    ESTER_CASCADE_MODE = "A" | "B"
    A — defoltnaya konfiguratsiya.
    B — vklyuchaet rasshirennyy kaskad (eta realizatsiya).
Pri lyuboy oshibke kaskad vozvraschaet validnyy rezultat i ne lomaet yadro.

Zemnoy abzats:
    from modules.thinking import cascade_closed
    print(cascade_closed.run_cascade("testovyy kaskad")["summary"])
# c=a+b
"""
from __future__ import annotations

import os
import math
import time
import traceback
from typing import Dict, Any, List, Tuple

from modules.memory import store
from modules.memory.vector import embed, search as vec_search
from modules.memory.events import record_event
from modules.context.thoughts_adapter import record_thought
from modules.thinking import pipelines as TP
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MAX_BRANCHES_A = 2
MAX_BRANCHES_B = 4
MAX_STEPS = 6


def _v2_enabled() -> bool:
    return (os.getenv("ESTER_CASCADE_V2", "0") or "0").strip().lower() in ("1", "true", "yes", "on")


def _v2_mode() -> str:
    m = (os.getenv("ESTER_CASCADE_V2_AB", "B") or "B").strip().upper()
    return "A" if m == "A" else "B"


def _risk_score(text: str) -> float:
    t = (text or "").lower()
    risk_terms = ["risk", "opas", "ugr", "kritich", "fail", "failure", "break", "security", "leak", "bug", "oshib"]
    for w in risk_terms:
        if w in t:
            return 0.8
    return 0.2


def _cost_score(text: str) -> float:
    # rough proxy: longer text => higher cost (0..1)
    n = len((text or "").strip())
    return min(1.0, max(0.0, n / 280.0))


def _relevance_score(goal: str, text: str) -> float:
    try:
        qv = embed(goal)
        tv = embed(text)
        # cosine in vector.search uses normalized vecs; we re-use vec_search for stability
        fake = [{"id": "t0", "text": text, "vec": tv}]
        ranked = vec_search(qv, fake, top_k=1) or []
        if ranked:
            return 1.0
    except Exception:
        pass
    return 0.5


def _novelty_score(text: str, recalled: List[Dict[str, Any]]) -> float:
    try:
        tv = embed(text)
        max_sim = 0.0
        for r in recalled or []:
            v = r.get("vec") or []
            if not isinstance(v, list) or not v:
                continue
            try:
                # cosine with normalized vectors
                sim = float(sum([tv[i] * v[i] for i in range(min(len(tv), len(v)))]))
            except Exception:
                sim = 0.0
            if sim > max_sim:
                max_sim = sim
        return max(0.0, min(1.0, 1.0 - max_sim))
    except Exception:
        return 0.5


def _decay(score: float, t_idx: int, cost: float) -> float:
    try:
        lt = float(os.getenv("ESTER_CASCADE_DECAY_TIME", "0.18") or 0.18)
        lc = float(os.getenv("ESTER_CASCADE_DECAY_COST", "0.9") or 0.9)
    except Exception:
        lt, lc = 0.18, 0.9
    return float(score) * math.exp(-lt * float(t_idx)) * math.exp(-lc * float(cost))


def score_branches(goal: str, branches: List[str], recalled: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, b in enumerate(branches or []):
        rel = _relevance_score(goal, b)
        nov = _novelty_score(b, recalled)
        risk = _risk_score(b)
        cost = _cost_score(b)
        # weighted base score
        base = (0.45 * rel) + (0.25 * nov) + (0.2 * (1.0 - risk)) + (0.1 * (1.0 - cost))
        dec = _decay(base, i, cost)
        out.append({
            "text": b,
            "relevance": round(rel, 3),
            "novelty": round(nov, 3),
            "risk": round(risk, 3),
            "cost": round(cost, 3),
            "score": round(base, 3),
            "decayed": round(dec, 3),
        })
    return out


def _should_save_residue(score: Dict[str, Any]) -> bool:
    mode = _v2_mode()
    if mode == "B":
        return True
    try:
        nov_thr = float(os.getenv("ESTER_CASCADE_RESIDUE_NOVELTY", "0.6") or 0.6)
        risk_thr = float(os.getenv("ESTER_CASCADE_RESIDUE_RISK", "0.6") or 0.6)
    except Exception:
        nov_thr, risk_thr = 0.6, 0.6
    return (float(score.get("novelty") or 0.0) >= nov_thr) or (float(score.get("risk") or 0.0) >= risk_thr)


def _residue_text(goal: str, branch: str, score: Dict[str, Any]) -> str:
    base = f"Vetka: {branch}"
    reason = "Otbroshena posle otsenki (nizkaya poleznost/zatukhanie)."
    signal = f"Signal: rel={score.get('relevance')} nov={score.get('novelty')} risk={score.get('risk')} cost={score.get('cost')}"
    if _v2_mode() == "B":
        return f"{base} / {reason} / {signal}"
    return f"{base} / {signal}"


def _save_residue(goal: str, branch: str, score: Dict[str, Any]) -> None:
    if not _should_save_residue(score):
        return
    try:
        text = _residue_text(goal, branch, score)
        meta = {
            "type": "branch_residue",
            "scope": "internal",
            "goal": goal,
            "branch": branch[:240],
            "scores": score,
            "ts": int(time.time()),
        }
        memory_add("fact", text, meta)
    except Exception:
        pass


def _mode() -> str:
    """Tekuschiy rezhim kaskada (A/B)."""
    m = (os.environ.get("ESTER_CASCADE_MODE", "A") or "A").strip().upper()
    return "B" if m == "B" else "A"


def _rank_branches(goal: str, hypotheses: List[str]) -> List[Tuple[str, float]]:
    """
    Ranzhirovanie gipotez po smyslovoy blizosti k tseli.
    Bezopasno: pri lyuboy oshibke vozvraschaet iskhodnyy poryadok.
    """
    try:
        qv = embed(goal)
        docs = []
        for i, h in enumerate(hypotheses):
            try:
                hv = embed(h)
            except Exception:
                hv = qv
            docs.append({"id": f"hyp{i}", "text": h, "vec": hv})
        ranked = vec_search(qv, docs, top_k=len(docs)) or []
        order = {r["text"]: idx for idx, r in enumerate(ranked)}
        out: List[Tuple[str, float]] = []
        n = max(1, len(hypotheses))
        for h in hypotheses:
            pos = order.get(h, n)
            score = 1.0 - (pos / n)
            out.append((h, float(score)))
        return out
    except Exception:
        return [(h, 1.0) for h in hypotheses]


def _branch_hypotheses(goal: str) -> List[str]:
    """Bazovye gipotezy dlya kaskada."""
    base = [
        f"nayti suschestvuyuschie resheniya dlya: {goal}",
        f"sobrat ogranicheniya i resursy dlya: {goal}",
        f"razbit zadachu na podzadachi: {goal}",
        f"sravnit alternativnye podkhody dlya: {goal}",
        f"provesti eksperiment dlya proverki: {goal}",
    ]
    k = MAX_BRANCHES_B if _mode() == "B" else MAX_BRANCHES_A
    return base[:k]


def _local_decision(goal: str, best_h: str, recalled_count: int) -> Dict[str, Any]:
    """
    Lokalnoe bezopasnoe reshenie.

    Evristika:
    - esli recalled_count > 0: opora na imeyuschiysya opyt;
    - inache: rekomendovat issledovanie i utochnenie trebovaniy.
    """
    if recalled_count > 0:
        choice = "ispolzovat nakoplennyy opyt i utochnit plan"
    else:
        choice = "issledovat zadachu i sobrat ogranicheniya"
    return {
        "mode": "local_decision",
        "goal": goal,
        "hypothesis": best_h,
        "recalled": recalled_count,
        "choice": choice,
        "summary": f"Dlya tseli '{goal}' vybrana strategiya: {choice}.",
    }


def run_cascade(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Zapustit kaskadnoe myshlenie dlya tseli.

    Vozvrat:
      {
        "ok": True/False,
        "goal": str,
        "steps": [...],
        "summary": str
      }
    """
    params = params or {}
    steps: List[Dict[str, Any]] = []

    # 1) Think
    steps.append({"stage": "think", "msg": f"Obdumyvayu tsel: {goal}"})
    try:
        record_event("cascade", "start", True, {"goal": goal})
        record_thought(goal, "start-cascade", True)
    except Exception:
        pass

    # 2) Recall
    try:
        recalled = store.query(goal, top_k=12)
    except Exception:
        recalled = []
    recalled_count = len(recalled)
    steps.append({"stage": "recall", "count": recalled_count})
    try:
        record_event("think", "recall", True, {"count": recalled_count})
    except Exception:
        pass

    # 3) Branch
    hypotheses = _branch_hypotheses(goal)
    ranked = _rank_branches(goal, hypotheses)
    ordered = [h for (h, _) in ranked] or hypotheses

    branch_scores = score_branches(goal, ordered, recalled) if _v2_enabled() else []
    # pick best by decayed score when v2
    if _v2_enabled() and branch_scores:
        branch_scores_sorted = sorted(branch_scores, key=lambda x: float(x.get("decayed") or 0.0), reverse=True)
        best_h = branch_scores_sorted[0]["text"]
        # residue for pruned branches
        for sc in branch_scores_sorted[1:]:
            _save_residue(goal, sc["text"], sc)
    else:
        best_h = ordered[0] if ordered else goal

    steps.append({"stage": "branch", "candidates": ordered, "scores": branch_scores})

    # 4) Plan
    try:
        best_h = best_h if best_h else (ordered[0] if ordered else goal)
    except Exception:
        best_h = goal

    plan_steps: List[Dict[str, Any]] = [
        {
            "op": "local_decision",
            "goal": goal,
            "hypothesis": best_h,
            "recalled": recalled_count,
        },
        {
            "op": "pipeline",
            "name": "analyze_text",
            "args": {"text": best_h},
        },
    ]
    steps.append({"stage": "plan", "steps": plan_steps})
    try:
        record_event("plan", "cascade-plan", True, {"len": len(plan_steps)})
    except Exception:
        pass

    # 5) Act
    results: List[Dict[str, Any]] = []
    for i, st in enumerate(plan_steps[:MAX_STEPS]):
        op = st.get("op")
        if op == "local_decision":
            try:
                decision = _local_decision(
                    st.get("goal", goal),
                    st.get("hypothesis", best_h),
                    int(st.get("recalled", recalled_count)),
                )
                results.append({"step": i, "name": "local_decision", "result": decision})
            except Exception as e:
                traceback.print_exc()
                results.append(
                    {"step": i, "name": "local_decision", "error": str(e)[:200]}
                )
        elif op == "pipeline":
            try:
                spec = TP.make_spec(st["name"], goal, st.get("args") or {})
                out = TP.run_pipeline(spec)
                results.append(
                    {
                        "step": i,
                        "name": st["name"],
                        "result": out.get("result", {}),
                        "took_sec": out.get("took_sec", 0),
                    }
                )
            except Exception as e:
                # Ne ronyaem kaskad pri oshibke payplayna.
                traceback.print_exc()
                results.append(
                    {"step": i, "name": st.get("name"), "error": str(e)[:200]}
                )
        else:
            results.append(
                {"step": i, "name": op or "unknown", "note": "skipped-unknown-op"}
            )

    steps.append({"stage": "act", "results": results})
    try:
        record_event("act", "cascade-execute", True, {"done": len(results)})
    except Exception:
        pass

    # 6) Reflect
    summary = None
    local_choice = None
    analyze_summary = None

    for r in results:
        res = r.get("result") or {}
        if isinstance(res, dict) and res.get("mode") == "local_decision" and not local_choice:
            local_choice = res.get("choice")
        if isinstance(res, dict) and res.get("mode") == "analyze_text" and not analyze_summary:
            analyze_summary = res.get("summary")

    if local_choice and analyze_summary:
        summary = f"{analyze_summary} / Rekomendatsiya: {local_choice}"
    elif local_choice:
        summary = f"Kaskad zavershen. Rekomendatsiya: {local_choice}"
    elif analyze_summary:
        summary = f"Kaskad zavershen. {analyze_summary}"
    else:
        summary = "Kaskad zavershen. Itog sformirovan."

    steps.append({"stage": "reflect", "summary": summary})
    try:
        record_thought(goal, summary, True)
        record_event("think", "cascade-reflect", True, {"summary": summary[:120]})
    except Exception:
        pass

    # Zapis v pamyat (kak dream/opyt)
    try:
        memory_add("dream", f"cascade: {goal}", {"summary": summary, "steps": len(steps)})
    except Exception:
        pass

    return {"ok": True, "goal": goal, "steps": steps, "summary": summary}
