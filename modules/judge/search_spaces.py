# -*- coding: utf-8 -*-
"""
Search spaces for EvoJudge. Closed-box, stdlib only.
We keep ranges conservative; all values are JSON-serializable.
"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DEFAULT_SPACE: Dict[str, Any] = {
    "llm": {
        "temperature": [0.1, 0.2, 0.3, 0.5, 0.7],
        "top_p": [0.6, 0.8, 0.9, 0.95],
        "max_tokens": [256, 512, 768, 1024],
        "stop": [[], ["\n\n"], ["\n", "###"]],
    },
    "rag": {
        "k": [2, 3, 4, 5, 8],
        "similarity": ["cosine", "l2"],
        "rerank": [False, True],
    },
    "judge": {
        "mode": ["majority", "weighted", "consensus"],
        "weight_local": [1.0, 1.5, 2.0],
        "weight_cloud": [0.5, 1.0, 1.5],
    },
    "tools": {
        "enable_web": [False],
        "enable_code": [True, False],
        "enable_calc": [True],
    },
}

def initial_population_size() -> int:
    return 8

def generations() -> int:
    return 6

def mutation_rate() -> float:
    return 0.25

def crossover_rate() -> float:
    return 0.5

def tournament_k() -> int:
    return 3