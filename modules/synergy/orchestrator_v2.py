# -*- coding: utf-8 -*-
"""
modules/synergy/orchestrator_v2.py — podbor roley v2 (tselevaya funktsiya, shtrafy, HARD-konstreynty, trace, kesh).

MOSTY:
- (Yavnyy) Summarnaya funktsiya: base=Σ suitability; penalties: nagruzka/nizkaya prigodnost/riski platformy/reaktsiya operatora;
  HARD: nesovmestimosti, platformu — tolko device, limit roley na agenta.
- (Skrytyy #1) Kesh prigodnostey 1–5 minut i idempotentnost po request_id (vozvraschaet tot zhe plan/trace).
- (Skrytyy #2) Lokalnye svapy (2-opt) s taymboksom i explainability-treysom shagov.

ZEMNOY ABZATs:
Orkestrator sobiraet «realno rabochuyu» komandu: ne tolko po tsifram prigodnosti, no i s uchetom riskov i pravil.
Plan obyasnimyy (trace), povtoryaemyy (idempotent) i ne «drozhit» ot melkikh izmeneniy.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import time

from modules.synergy.state_store import STORE
from modules.synergy.role_model import fit_roles_ext
from modules.synergy.capability_infer import infer_capabilities
from modules.synergy.plan_cache import CACHE
from modules.synergy.models import RoleName
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ------------------------ vspomogatelnye shtuki ------------------------

def _agent_kind(a: Dict[str, Any]) -> str:
    return (a.get("kind") or "").lower()

def _updated_at(a: Dict[str, Any]) -> float:
    return float(a.get("updated_at") or 0.0)

def _is_device(a: Dict[str, Any]) -> bool:
    return _agent_kind(a) == "device"

def _profile(a: Dict[str, Any]) -> Dict[str, Any]:
    return dict(a.get("profile") or {})

def _cap(a: Dict[str, Any]) -> Dict[str, float]:
    return infer_capabilities(a)

def _scores_for(a: Dict[str, Any]) -> Dict[str, float]:
    # Keshiruem prigodnosti po updated_at
    return CACHE.get_scores(a["id"], _updated_at(a), lambda: fit_roles_ext(a))

# ------------------------ tsel/shtrafy/konstreynty ------------------------

def _hard_violations(assigned: Dict[str, str], agents_by_id: Dict[str, Dict[str, Any]], policies: Dict[str, Any]) -> List[str]:
    vio: List[str] = []
    # 1) Platforma dolzhna byt device
    if RoleName.platform.value in assigned:
        aid = assigned[RoleName.platform.value]
        if not _is_device(agents_by_id.get(aid, {})):
            vio.append("platform_must_be_device")
    # 2) Nesovmestimosti (napr., operator/strategist ne dolzhny sovpadat)
    incompat = [(str(a), str(b)) for a,b in policies.get("incompat", [])]
    for a,b in incompat:
        if a in assigned and b in assigned and assigned[a] == assigned[b]:
            vio.append(f"incompat:{a}+{b}")
    # 3) Limit roley na agenta
    max_roles = int(policies.get("max_roles_per_agent", 2))
    counts: Dict[str,int] = {}
    for r, aid in assigned.items():
        counts[aid] = counts.get(aid, 0) + 1
    for aid, n in counts.items():
        if n > max_roles:
            vio.append(f"too_many_roles:{aid}:{n}")
    return vio

def _penalties(assigned: Dict[str, str], scores: Dict[str, Dict[str, float]], agents_by_id: Dict[str, Dict[str, Any]], policies: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    p_total = 0.0
    p_breakdown: Dict[str, float] = {}
    # Nagruzka: za kazhduyu vtoruyu i dalee rol — myagkiy shtraf
    counts: Dict[str,int] = {}
    for r, aid in assigned.items():
        counts[aid] = counts.get(aid, 0) + 1
    for aid, n in counts.items():
        if n > 1:
            pen = 0.05 * (n - 1)
            p_total += pen
            p_breakdown[f"load:{aid}"] = p_breakdown.get(f"load:{aid}", 0.0) + pen
    # Nizkaya prigodnost: esli score < 0.3 — shtraf
    for r, aid in assigned.items():
        sc = scores.get(aid, {}).get(r, 0.0)
        if sc < 0.3:
            pen = (0.3 - sc) * 0.3
            p_total += pen
            p_breakdown[f"lowfit:{r}:{aid}"] = pen
    # Riski platformy: nizkoe vremya/vysokaya latentnost
    for r, aid in assigned.items():
        if r != RoleName.platform.value:
            continue
        ag = agents_by_id.get(aid, {})
        prof = _profile(ag)
        ft = float(prof.get("flight_time_min") or 0.0)
        lat = float(prof.get("latency_ms") or 0.0)
        if ft and ft < 12.0:
            pen = (12.0 - ft) * 0.01  # do ~0.12
            p_total += pen; p_breakdown["platform:low_flight"] = pen
        if lat and lat > 200.0:
            pen = min(0.3, (lat - 200.0) * 0.001)  # do 0.3
            p_total += pen; p_breakdown["platform:high_latency"] = pen
    # Reaktsiya operatora
    for r, aid in assigned.items():
        if r != RoleName.operator.value:
            continue
        reac = _cap(agents_by_id.get(aid, {})).get("reaction", 0.0)
        if reac < 0.4:
            pen = (0.4 - reac) * 0.2
            p_total += pen; p_breakdown["operator:low_reaction"] = pen
    return p_total, p_breakdown

def _objective(assigned: Dict[str, str], scores: Dict[str, Dict[str, float]], agents_by_id: Dict[str, Dict[str, Any]], policies: Dict[str, Any]) -> Tuple[float, float, List[str], Dict[str,float]]:
    base = sum(scores.get(aid, {}).get(role, 0.0) for role, aid in assigned.items())
    vio = _hard_violations(assigned, agents_by_id, policies)
    if vio:
        # beskonechnyy shtraf → ochen malenkaya otsenka
        return -1e9, 0.0, vio, {}
    pen, breakdown = _penalties(assigned, scores, agents_by_id, policies)
    total = base - pen
    return total, pen, [], breakdown

# ------------------------ algoritm naznacheniya ------------------------

def _initial_greedy(roles: List[str], agents: List[Dict[str, Any]], scores: Dict[str, Dict[str, float]], frozen: Dict[str, str]) -> Dict[str, str]:
    assigned: Dict[str, str] = dict(frozen)
    taken: Dict[str, int] = {}
    for r, aid in frozen.items():
        taken[aid] = taken.get(aid, 0) + 1
    for role in roles:
        if role in assigned:
            continue
        best_id, best_s = None, -1.0
        for a in agents:
            s = scores.get(a["id"], {}).get(role, 0.0) - 0.08 * taken.get(a["id"], 0)
            if s > best_s:
                best_id, best_s = a["id"], s
        if best_id:
            assigned[role] = best_id
            taken[best_id] = taken.get(best_id, 0) + 1
    return assigned

def _refine_swaps(roles: List[str], agents_by_id: Dict[str, Dict[str, Any]], assigned: Dict[str, str], scores: Dict[str, Dict[str, float]], policies: Dict[str, Any], timebox_ms: int = 40, max_iters: int = 50, steps: List[Dict[str, Any]] | None = None) -> Dict[str, str]:
    start = time.monotonic()
    cur = dict(assigned)
    cur_score, _, _, _ = _objective(cur, scores, agents_by_id, policies)
    if steps is not None:
        steps.append({"description": f"initial_score={round(cur_score,3)}", "delta_score": 0.0})
    roles_idx = list(range(len(roles)))
    for it in range(max_iters):
        improved = False
        for i in roles_idx:
            for j in range(i + 1, len(roles)):
                r1, r2 = roles[i], roles[j]
                a1, a2 = cur.get(r1), cur.get(r2)
                if not a1 or not a2 or a1 == a2:
                    continue
                trial = dict(cur)
                trial[r1], trial[r2] = a2, a1
                t_score, _, vio, _ = _objective(trial, scores, agents_by_id, policies)
                if vio:
                    continue
                if t_score > cur_score + 1e-6:
                    delta = t_score - cur_score
                    cur, cur_score = trial, t_score
                    improved = True
                    if steps is not None:
                        steps.append({"description": f"swap:{r1}<->{r2}", "delta_score": round(delta, 4)})
        if not improved or (time.monotonic() - start) * 1000.0 > timebox_ms:
            break
    return cur

# ------------------------ publichnyy API ------------------------

def assign_v2(team_name: str, overrides: Dict[str, str] | None = None, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Podbor roley (idempotent po request_id). Format otveta sovmestim s predyduschey versiey + dop. polya:
    - total: itogovaya otsenka plana
    - penalty: summa shtrafov
    - violations: spisok HARD-narusheniy (esli est)
    - steps: trace optimizatsii (spisok dict'ov)
    - trace_id: identifikator trassy
    """
    # Idempotentnost
    cached = CACHE.get_plan(request_id)
    if cached:
        return dict(cached)

    team = STORE.get_team(team_name)
    if not team:
        return {"ok": False, "error": "team_not_found"}

    # Politiki
    policies = {
        "max_roles_per_agent": 2,
        "incompat": [["operator","strategist"]],
    }
    # Vytaskivaem potentsialnye roli
    roles: List[str] = list(team.get("roles_needed", []))
    if not roles:
        # fallback: bazovyy nabor
        roles = [RoleName.strategist.value, RoleName.operator.value, RoleName.platform.value]

    # Agenty i prigodnosti (s keshem)
    agents = STORE.list_agents()
    agents_by_id = {a["id"]: a for a in agents}
    scores: Dict[str, Dict[str, float]] = {a["id"]: _scores_for(a) for a in agents}

    # Overraydy (zamorozki)
    frozen = dict((team.get("overrides") or {}))
    if overrides:
        frozen.update({k: v for k, v in overrides.items() if v})

    # Nachalnyy plan i dooptimizatsiya
    plan0 = _initial_greedy(roles, agents, scores, frozen)
    steps: List[Dict[str, Any]] = []
    plan = _refine_swaps(roles, agents_by_id, plan0, scores, policies, steps=steps)

    total, penalty, vio, pen_break = _objective(plan, scores, agents_by_id, policies)
    trace_id = f"trace:{int(time.time()*1000)}"

    # Sokhranyaem v STORE (kak i ranshe)
    t = STORE.get_team(team_name) or {}
    t.setdefault("assigned", {}).update(plan)
    t["overrides"] = frozen
    STORE._teams[team_name] = t

    res = {
        "ok": True,
        "team": team_name,
        "assigned": plan,
        "scores": scores,
        "overrides": frozen,
        "total": total,
        "penalty": penalty,
        "violations": vio,
        "penalty_breakdown": pen_break,
        "steps": steps,
        "trace_id": trace_id,
    }

    # Idempotentnyy kesh
    CACHE.put_plan(request_id, res)
    return res