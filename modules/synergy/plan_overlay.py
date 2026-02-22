# -*- coding: utf-8 -*-
"""
modules/synergy/plan_overlay.py — «overley» sovetnika poverkh proizvolnogo plana (tolko metadannye).

MOSTY:
- (Yavnyy) build_overlay(plan, extras, alpha) → slovar metadannykh k kandidatam: bias, labels, why, synergy_avg, color_hint.
- (Skrytyy #1) Ne menyaet iskhodnyy plan — tolko vozvraschaet «prosloyku» dlya UI/treysa i cheloveko-ponyatnykh obyasneniy.
- (Skrytyy #2) Degradiruet akkuratno: esli format plana neizvesten, pytaetsya vytaschit candidates[] po klyucham.

ZEMNOY ABZATs:
Reshenie orkestratora ostaetsya «kak est». My lish podsvechivaem, u kogo est stikhiynoe preimuschestvo (profil, sygrannost),
chtoby operator bystree prinyal vzveshennoe reshenie.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _find_candidates_in_plan(plan: Dict[str, Any]) -> List[str]:
    # Nakhodim agent_id vnutri "candidates":[{"agent_id":...}, ...] dlya vsekh shagov
    ids: List[str] = []
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if isinstance(steps, list):
        for st in steps:
            cand = (st or {}).get("candidates")
            if isinstance(cand, list):
                for c in cand:
                    a = (c or {}).get("agent_id")
                    if isinstance(a, str):
                        ids.append(a)
    # fallback: team[]
    team = plan.get("team") if isinstance(plan, dict) else None
    if isinstance(team, list):
        for t in team:
            if isinstance(t, str):
                ids.append(t)
    return list(dict.fromkeys(ids))

def _avg_pairwise(agent: str, team: List[str], pairwise: Dict[str, float]) -> float:
    if not team: return 0.0
    sc = 0.0; n = 0
    for b in team:
        if b == agent: continue
        k = f"{agent}__{b}" if agent < b else f"{b}__{agent}"
        if k in pairwise:
            sc += float(pairwise[k]); n += 1
    return (sc / n) if n else 0.0

def _color_from_bias_synergy(bias: float, syn: float) -> str:
    """
    Vozvraschaet rekomendatsiyu tsveta dlya UI (light CSS):
      '++' / '+' / '0' / '-' — chem silnee zelenyy, tem yavnee podskazka.
    """
    # normalizuem v [-1..+1]
    x = max(-1.0, min(1.0, bias*2.5 + syn))  # slegka usilivaem bias
    if x >= 0.75: return "++"
    if x >= 0.30: return "+"
    if x <= -0.50: return "-"
    return "0"

def build_overlay(plan: Dict[str, Any], extras: Dict[str, Any], alpha: float | None = None) -> Dict[str, Any]:
    """
    Vozvraschaet overlay-metadannye, ne menyaya iskhodnyy plan.
    extras: {"advice":[...] (normalized 0..1), "team_bonus":float, "pairwise":{a__b:w}}
    alpha: ves dlya "bias" (po umolchaniyu ENV ADVISOR_BLEND).
    """
    alpha = float(alpha if alpha is not None else float(os.getenv("ADVISOR_BLEND","0.2") or 0.2))
    candidates = _find_candidates_in_plan(plan)
    advice = extras.get("advice") or []
    team = plan.get("team") or []
    pairwise = extras.get("pairwise") or {}

    idx = {a["agent_id"]: a for a in advice if isinstance(a, dict) and "agent_id" in a}
    out: Dict[str, Any] = {"team_bonus": float(extras.get("team_bonus") or 0.0), "candidates": {}}

    for ag in candidates:
        a = idx.get(ag)
        norm = float(a.get("normalized") or 0.5) if a else 0.5
        bias = alpha * ((norm - 0.5)*2.0)  # -alpha..+alpha
        syn = _avg_pairwise(ag, team, pairwise)
        color = _color_from_bias_synergy(bias, syn)
        labels = a.get("labels",[]) if a else []
        why = a.get("why",[]) if a else []
        out["candidates"][ag] = {
            "advice_bias": round(bias, 4),
            "synergy_avg": round(float(syn), 4),
            "color_hint": color,
            "labels": labels[:4],
            "why": why
        }
    return out