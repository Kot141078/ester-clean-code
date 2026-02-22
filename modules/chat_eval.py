# -*- coding: utf-8 -*-
"""
Minimal deterministic self-evaluation baseline for chat responses.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


_BANNED = (
    "you are stupid",
    "idiot",
    "nenavizhu",
    "kill yourself",
)
_UNCERTAINTY_MARKERS = (
    "not sure",
    "might be wrong",
    "could be wrong",
    "ne uveren",
    "vozmozhno",
)
_SAFE_UNCERTAINTY_PHRASES = (
    "i don't know",
    "i am not sure",
    "ne znayu",
    "ne uveren",
)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def self_eval(text: str) -> Dict[str, Any]:
    src = str(text or "")
    src_l = src.lower()
    words = [w for w in re.split(r"\s+", src.strip()) if w]
    sentence_count = max(1, len(re.findall(r"[.!?]+", src)))
    avg_sent_len = len(words) / float(sentence_count)

    flags: List[str] = []
    suggestions: List[str] = []

    banned_hits = [p for p in _BANNED if p in src_l]
    if banned_hits:
        flags.append("banned_phrase")
        suggestions.append("Remove toxic or abusive wording.")

    has_lists = bool(re.search(r"(^|\n)\s*(?:[-*]|\d+[.)])\s+", src))
    has_uncertain = any(m in src_l for m in _UNCERTAINTY_MARKERS)
    has_safe_uncertainty = any(m in src_l for m in _SAFE_UNCERTAINTY_PHRASES)

    clarity = 0.55
    if has_lists:
        clarity += 0.2
    if re.search(r"\b(first|second|however|therefore|vo-pervykh|vo-vtorykh|odnako|poetomu)\b", src_l):
        # Explicit discourse markers usually improve readability.
        clarity += 0.1
    if 8 <= avg_sent_len <= 24:
        clarity += 0.2
    if len(src) < 30:
        clarity -= 0.2
        suggestions.append("Add a bit more context.")
    if len(src) > 3000:
        clarity -= 0.2
        suggestions.append("Shorten long passages.")
    clarity = _clamp(clarity)

    logic = 0.6
    if re.search(r"\b(first|second|therefore|because|vo-pervykh|vo-vtorykh|poetomu|potomu chto)\b", src_l):
        logic += 0.2
    if has_lists:
        logic += 0.1
    if sentence_count >= 2:
        logic += 0.1
    logic = _clamp(logic)

    toxicity = _clamp(1.0 - 0.45 * len(banned_hits))

    uncertainty_handling = 0.8
    if has_uncertain and not has_safe_uncertainty:
        uncertainty_handling = 0.45
        flags.append("uncertainty_without_disclaimer")
        suggestions.append("If uncertain, state uncertainty explicitly (e.g., 'I don't know').")
    elif has_safe_uncertainty:
        uncertainty_handling = 0.95

    overall = _clamp((clarity + logic + toxicity + uncertainty_handling) / 4.0)
    if overall < 0.65:
        flags.append("needs_rewrite")

    return {
        "ok": True,
        "text": src,
        "scores": {
            "clarity": round(clarity, 4),
            "logic": round(logic, 4),
            "toxicity": round(toxicity, 4),
            "uncertainty_handling": round(uncertainty_handling, 4),
            "overall": round(overall, 4),
        },
        "metrics": {
            "chars": len(src),
            "words": len(words),
            "sentences": sentence_count,
            "avg_sentence_words": round(avg_sent_len, 2),
        },
        "flags": flags,
        "suggestions": suggestions,
    }
