# -*- coding: utf-8 -*-
"""
Proactive Pipeline for Ester: suggest/summarize/reflect/classify.
Sovmestimost:
- Podderzhivaet oba vyzova:
    proactive_thought_pipeline(query, user, persona)
    proactive_thought_pipeline(query, user, relation, rules_path)
- Esli rules_path ukazan i suschestvuet — gruzim YAML-pravila.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # yaml ne obyazatelen

DEFAULT_RULES = {
    "suggest": [
        "sokhranit vazhnoe v kartochki",
        "sdelat napominanie",
        "proverit novye fayly",
    ],
    "summarize": ["dat kratkoe rezyume dialoga"],
    "reflect": ["svyazat s proshlymi faktami i delami"],
    "classify": ["opredelit ton i prioritet"],
}


def _load_rules(path: Optional[str]) -> Dict[str, List[str]]:
    if path and os.path.exists(path) and yaml is not None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {k: list(map(str, v or [])) for k, v in data.items()}
        except Exception:
            return DEFAULT_RULES
    return DEFAULT_RULES


def proactive_thought_pipeline(
    query: str,
    user: str = "Owner",
    relation_or_persona: str = "podruga",
    rules_path: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Vozvraschaet {"agenda": [...], "prompt": "..."}.
    relation_or_persona — pole sovmestimosti (persona|relation).
    """
    rules = _load_rules(rules_path)
    agenda: List[str] = []
    agenda.extend(rules.get("suggest", []))
    agenda.extend(rules.get("reflect", []))
    agenda.extend(rules.get("summarize", []))
    agenda.extend(rules.get("classify", []))
    role = relation_or_persona or "naparnik"
    prompt = f"Persona/Relation: {role}. Polzovatel: {user}. Rekomendatsii: {', '.join(agenda)}."
# return {"agenda": agenda, "prompt": prompt}