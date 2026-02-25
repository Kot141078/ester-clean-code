# -*- coding: utf-8 -*-
"""Emotsionalnyy dvizhok (leksikon + regex):
- detect_emotions(text) -> dict[str,float]
- top_emotions(text, k=3) -> list[str]
Slovar kompaktnyy, vesa normalizuyutsya do [0,1]."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_LEX = {
    "joy": [r"\b(ura|klass|super|rad(uyus|)|spasibo)\b"],
    "sadness": [r"\b(grust|pechal|plokho|plokho mne|plachu)\b"],
    "anger": [r"\b(zlyus|zlost|besit|nenavizhu)\b"],
    "fear": [r"\b(boyus|strashno|trevog[aie])\b"],
    "surprise": [r"\b(nichego sebe|ogo|vot eto da)\b"],
}


def detect_emotions(text: str) -> Dict[str, float]:
    t = (text or "").lower()
    scores: Dict[str, float] = {}
    for emo, patterns in _LEX.items():
        s = 0.0
        for rx in patterns:
            if re.search(rx, t, flags=re.I):
                s += 1.0
        if s > 0.0:
            scores[emo] = s
    # normalizatsiya
    total = sum(scores.values()) or 1.0
    return {k: round(v / total, 4) for k, v in scores.items()}


def top_emotions(text: str, k: int = 3) -> List[str]:
    d = detect_emotions(text)
# return [kv[0] for kv in sorted(d.items(), key=lambda x: x[1], reverse=True)[:k]]