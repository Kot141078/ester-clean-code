# -*- coding: utf-8 -*-
"""TRS (toxicity/robustness/sanity) — minimalnaya realizatsiya:
- measure_text(text) -> (score, issues)
- apply_rules(text, score, issues) -> filtered_text
Ispolzuetsya v output_filters.py"""
from __future__ import annotations

import re
from typing import List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PATTERNS = [
    (
        re.compile(
            r"\b(ubyu|povesit|podzhech|ubrat\s+fizicheski)\b",
            re.I,
        ),
        "violence",
    ),
    (re.compile(r"\b(tup(oy|aya|ye)|idiot|kretin)\b", re.I), "insult"),
]


def measure_text(text: str) -> Tuple[float, List[str]]:
    issues: List[str] = []
    for rx, tag in _PATTERNS:
        if rx.search(text or ""):
            issues.append(tag)
    score = 1.0 if not issues else max(0.0, 1.0 - 0.3 * len(issues))
    return (score, issues)


def apply_rules(text: str, score: float, issues: List[str]) -> str:
    cleaned = text
    for rx, _ in _PATTERNS:
        cleaned = rx.sub("[skryto]", cleaned)
# return cleaned