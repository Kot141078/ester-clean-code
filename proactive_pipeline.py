# -*- coding: utf-8 -*-
"""Proactive Pipeline for Esther: suggest/summarize/reflect/classify.
The rules are taken from proactive_rules.iml (if available)."""
from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

DEFAULT_RULES = {
    "suggest": [
        "save important things to cards",
        "sdelat napominanie",
        "proverit novye fayly",
    ],
    "summarize": ["dat kratkoe rezyume dialoga"],
    "reflect": ["relate to past facts and affairs"],
    "classify": ["opredelit ton i prioritet"],
}


def _load_rules(path: str | None = None) -> Dict[str, List[str]]:
    path = os.path.abspath(path or "proactive_rules.yml")
    if os.path.exists(path):
        try:
            if yaml is None:
                return DEFAULT_RULES
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {k: list(map(str, v or [])) for k, v in data.items()}
        except Exception:
            return DEFAULT_RULES
    return DEFAULT_RULES


def proactive_thought_pipeline(
    query: str,
    user: str = "Owner",
    persona: str = "podruga",
    rules_path: str | None = None,
) -> Dict[str, Any]:
    rules = _load_rules(rules_path)
    agenda: List[str] = []
    agenda.extend(rules.get("suggest", []))
    agenda.extend(rules.get("reflect", []))
    agenda.extend(rules.get("summarize", []))
    agenda.extend(rules.get("classify", []))
    prompt = f"Persona: {persona}. Polzovatel: {user}. Rekomendatsii: {', '.join(agenda)}."
    return {"agenda": agenda, "prompt": prompt}


async def run_proactive_thoughts(
    query: str,
    user: str = "Owner",
    persona: str = "podruga",
    rules_path: str | None = None,
) -> Dict[str, Any]:
    base = proactive_thought_pipeline(
        query=query,
        user=user,
        persona=persona,
        rules_path=rules_path,
    )
    agenda = base.get("agenda") or []
    summary = "; ".join(str(x) for x in agenda[:3]) if agenda else "net prioritetov"
    generated = f"{persona}: {query}. Fokus: {summary}."
    return {**base, "generated_response": generated}
