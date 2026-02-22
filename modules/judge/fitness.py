# -*- coding: utf-8 -*-
"""
Fitness calculators and aggregation for EvoJudge.
"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def fold_scores(items: List[Dict[str, Any]], weights: Dict[str, float]) -> Dict[str, float]:
    """Aggregate per-task metrics into a single fitness vector and scalar score.
    items: [{utility, accuracy, time_sec, err_rate, tokens_prompt, tokens_gen}]
    weights: {'utility': w1, 'accuracy': w2, 'time_sec': w3, 'err_rate': w4, ...}
    """
    n = max(1, len(items))
    agg = {
        "utility": sum(float(x.get("utility", 0.0)) for x in items) / n,
        "accuracy": sum(float(x.get("accuracy", 0.0)) for x in items) / n,
        "time_sec": sum(float(x.get("time_sec", 0.0)) for x in items) / n,
        "err_rate": sum(float(x.get("err_rate", 0.0)) for x in items) / n,
        "tokens_prompt": sum(float(x.get("tokens_prompt", 0.0)) for x in items) / n,
        "tokens_gen": sum(float(x.get("tokens_gen", 0.0)) for x in items) / n,
    }
    cost_time = 1.0 / (1.0 + agg["time_sec"])
    cost_errs = 1.0 - min(1.0, agg["err_rate"])
    cost_tokens = 1.0 / (1.0 + (agg["tokens_prompt"] + agg["tokens_gen"]) / 512.0)
    score = (
        weights.get("utility", 1.0) * agg["utility"] +
        weights.get("accuracy", 1.0) * agg["accuracy"] +
        weights.get("cost_time", 0.5) * cost_time +
        weights.get("cost_errs", 0.75) * cost_errs +
        weights.get("cost_tokens", 0.25) * cost_tokens
    )
    return {"score": score, **agg}

DEFAULT_WEIGHTS = {
    "utility": 1.0,
    "accuracy": 1.0,
    "cost_time": 0.5,
    "cost_errs": 0.75,
    "cost_tokens": 0.25,
}