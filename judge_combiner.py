# -*- coding: utf-8 -*-
"""
judge_combiner.py — modul finalnogo sinteza otvetov.
Podderzhivaet tri rezhima:
- local: tolko lokalnye otvety (vybor luchshego po evristike soglasovannosti)
- cloud: lokalnye otvety slivayutsya «sudey» (oblachnaya LLM)
- judge: yavnyy vybor sudi (oblachnyy ili setevoy agent)

Sovmestimo s imeyuschimsya reestrom provayderov (providers.ProviderRegistry).
Bez zaglushek: logika realno rabotaet pri nalichii provayderov.
"""
from __future__ import annotations

import statistics
import time
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MERGE_SYSTEM_PROMPT = (
    "Ty — strogiy moderator-redaktor. Tebe peredan iskhodnyy zapros polzovatelya i neskolko otvetov ot raznykh modeley. "
    "Tvoya zadacha: 1) vyyavit obschee, 2) podcherknut raskhozhdeniya, 3) sintezirovat itogovyy, maksimalno tochnyy i kratkiy otvet. "
    "Ne povtoryay vse doslovno — vyday edinyy otvet. Esli fakty raskhodyatsya, ukazhi neopredelennosti i predlozhi shagi proverki."
)


def _score_answer(ans: str) -> float:
    """Prostaya evristika kachestva otveta dlya vybora luchshego lokalnogo varianta.
    Kombiniruem dlinu (v razumnykh predelakh) i strukturirovannost (kol-vo punktov, zagolovkov).
    """
    if not ans:
        return 0.0
    length = min(len(ans), 4000) / 4000.0
    bullets = ans.count("\n- ") + ans.count("\n* ") + ans.count("\n1.")
    headers = sum(1 for ch in ans.splitlines() if ch.strip().endswith(":"))
    punctuation = sum(ans.count(p) for p in [".", "!", "?", ";", ":"])
    structure = (bullets + headers) / 12.0
    punctuation_score = min(punctuation / 80.0, 1.0)
    return 0.55 * length + 0.30 * structure + 0.15 * punctuation_score


def pick_best_local(answers: List[str]) -> Tuple[str, Dict[str, Any]]:
    scores = [_score_answer(a) for a in answers]
    if not scores:
        return "", {"strategy": "none", "scores": [], "picked_index": None}
    max_i = max(range(len(scores)), key=lambda i: scores[i])
    meta = {
        "strategy": "heuristic_local",
        "scores": scores,
        "picked_index": max_i,
        "mean_score": statistics.mean(scores) if scores else 0.0,
    }
    return answers[max_i], meta


def _format_merge_messages(prompt: str, answers: List[str]) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": MERGE_SYSTEM_PROMPT}]
    messages.append(
        {
            "role": "user",
            "content": f"Iskhodnyy zapros polzovatelya:\n{prompt.strip()}".strip(),
        }
    )
    for i, a in enumerate(answers, 1):
        messages.append({"role": "user", "content": f"Variant #{i}:\n{a.strip()}"})
    messages.append(
        {
            "role": "user",
            "content": "Sinteziruy odin itogovyy otvet kak opytnyy redaktor.",
        }
    )
    return messages


def combine_answers(
    *,
    prompt: str,
    local_answers: List[str],
    mode: str = "local",
    registry=None,
    judge_name: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1200,
) -> Dict[str, Any]:
    """Glavnaya funktsiya sinteza.
    Vozvraschaet dict: { 'final', 'mode', 'merge_meta', 'used_judge', 'used_candidates' }
    """
    t0 = time.time()
    if mode == "local" or not registry:
        final, meta = pick_best_local(local_answers)
        return {
            "final": final,
            "mode": "local",
            "merge_meta": meta,
            "used_judge": None,
            "used_candidates": len(local_answers),
            "duration_ms": int((time.time() - t0) * 1000),
        }

    # Vybor sudi
    if mode == "cloud" and judge_name is None:
        judge_name = getattr(registry, "default_cloud", None) or "openai"
    if mode == "judge" and not judge_name:
        judge_name = registry.default_cloud if hasattr(registry, "default_cloud") else "openai"

    messages = _format_merge_messages(prompt, local_answers)
    
    # Vyzov cherez registry (predpolagaetsya nalichie metoda chat)
    merged = registry.chat(
        messages=messages,
        provider_name=judge_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    return {
        "final": merged,
        "mode": mode,
        "merge_meta": {"strategy": "llm_judge_merge", "candidates": len(local_answers)},
        "used_judge": judge_name,
        "used_candidates": len(local_answers),
        "duration_ms": int((time.time() - t0) * 1000),
    }