# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

try:
    from .hypothesis_engine import format_hypotheses_block, generate_hypotheses_from_text
    from .temporal_helper import get_system_datetime
except ImportError:
    from hypothesis_engine import (
        generate_hypotheses_from_text,
        format_hypotheses_block,
    )
    from temporal_helper import get_system_datetime

from emotional_engine import EmotionalEngine

emotional_engine = EmotionalEngine()

from structured_memory import StructuredMemory

memory = StructuredMemory("ester_memory.json")

from search_agent import SearchAgent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

search_agent = SearchAgent()

USER_NAME = "Owner"
PERSONA = "personalnyy AI-kompanon i podruga"
SYSTEM_PROMPT_TEMPLATE = (
    "Ty — Ester, {persona} {user_name}.\n"
    "Otvechay druzhelyubno, berezhno i po delu.\n"
    "Ne nachinay otvet s obrascheniya k sobesedniku (naprimer, 'Privet, Owner!').\n"
    "Srazu perekhodi k suti. Esli nuzhno, mozhesh ispolzovat imya v seredine otveta.\n"
    "Ya budu dumat shag za shagom.\n"
)


def _render_context_block(
    mem_entries: Optional[List[Dict[str, Any]]],
    web_snippets: Optional[List[Dict[str, Any]]],
) -> str:
    lines: List[str] = []
    if mem_entries:
        lines.append(
            "Kontekst iz pamyati (poslednie sovpadeniya):"
        )
        for i, m in enumerate(mem_entries[:5], 1):
            q = (m.get("query") or "")[:180].replace("\n", " ")
            a = (m.get("answer") or "")[:220].replace("\n", " ")
            score = m.get("semantic_score")
            score_str = f" (semantic={float(score):.3f})" if isinstance(score, (float, int)) else ""
            lines.append(f"{i}. Q: {q} | A: {a}{score_str}")
    if web_snippets:
        lines.append("\nKontekst iz veb-poiska:")
        for i, it in enumerate(web_snippets[:5], 1):
            title = it.get("title") or it.get("name") or ""
            snippet = (it.get("snippet") or it.get("summary") or "")[:280].replace("\n", " ")
            src = it.get("link") or it.get("url") or ""
            lines.append(f"{i}. {title} — {snippet} (istochnik: {src})")
    return "\n".join(lines) if lines else "—"


def _needs_web_search(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "kto takoy",
        "chto takoe",
        "kogda",
        "gde nakhoditsya",
        "kurs",
        "tsena",
        "novosti",
        "poslednie",
        "kak sdelat",
        "skolko stoit",
        "poslednie sobytiya",
        "vikipediya",
        "istochnik",
        "ssylka",
        "https://",
        "http://",
        "?",
        "reliz",
        "obnovlenie",
        "pogoda",
        "prognoz",
        "temperatura",
        "osadki",
        "shtorm",
        "weather",
        "forecast",
        "obzor",
        "itogi",
        "svodka",
    ]
    return any(x in t for x in triggers)


def _web_search_sync(
    query: str, n: int = 3, date_restrict: Optional[str] = None
) -> List[Dict[str, Any]]:
    try:
        return asyncio.run(search_agent.search(query, n))
    except (TypeError, RuntimeError):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(search_agent.search(query, n))
            except TypeError:
                return loop.run_until_complete(search_agent.search(query, n))
        finally:
            loop.close()


async def proactive_thought_pipeline(
    user_query: str, user_name: str, persona: str
) -> Dict[str, Any]:
    emotional_state = emotional_engine.detect_emotions(user_query)
    emotions_dict = {
        "anxiety": emotional_state.get("anxiety", 0.0),
        "joy": emotional_state.get("joy", 0.0),
        "interest": emotional_state.get("interest", 0.0),
    }
    emotions_list = [k for k, v in emotions_dict.items() if v > 0.0]

    hypotheses: List[str] = generate_hypotheses_from_text(user_query) or []
    hypotheses_lower = [str(h).lower() for h in hypotheses]

    relevant_memories = memory.search_semantic(user_query, limit=5)
    if not relevant_memories:
        relevant_memories = memory.last_entries(5)

    web_results: List[Dict[str, Any]] = []
    will_search = _needs_web_search(user_query) or any(
        "proaktivnyy poisk" in h for h in hypotheses_lower
    )
    if will_search:
        try:
            web_results = _web_search_sync(user_query, n=3)
        except Exception:
            web_results = []

    now = get_system_datetime("UTC")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(persona=persona, user_name=user_name)

    thoughts = "<|im_start|>system\n"
    thoughts += system_prompt
    thoughts += f"Seychas {now['date']} {now['time']} ({now['tz']}).\n"
    thoughts += "Ya budu dumat shag za shagom.\n\n"

    thoughts += "<thought>\n"
    thoughts += f"Analiziruyu zapros: '{user_query}'\n"
    thoughts += f"Obnaruzheny emotsii: {', '.join(emotions_list) if emotions_list else 'ne opredeleny'}.\n"
    thoughts += f"Generiruyu gipotezy: {len(hypotheses)} shtuk.\n"
    thoughts += "Ispolzuyu semanticheskiy poisk po vektornoy baze dannykh dlya poiska v pamyati.\n"
    if relevant_memories:
        thoughts += f"Proveryayu kontekst iz pamyati: naydeno {len(relevant_memories)} zapisey.\n"
    else:
        thoughts += "Proveryayu kontekst iz pamyati: relevantnyy kontekst ne nayden.\n"
    if will_search:
        thoughts += "Trebuetsya aktualnaya informatsiya — initsiiruyu veb-poisk.\n"
    else:
        thoughts += "Veb-poisk ne trebuetsya. Otvet budet osnovan na pamyati i logike.\n"
    thoughts += "</thought>\n\n"

    context_block = _render_context_block(relevant_memories, web_results)
    hypotheses_block = format_hypotheses_block(hypotheses) or ""

    prompt = (
        f"{thoughts}"
        f"{hypotheses_block}\n"
        "<context>\n"
        f"{context_block}\n"
        "</context>\n"
        "<|im_start|>user\n"
        f"{user_query}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    return {
        "prompt": prompt,
        "thought_process": thoughts,
        "web_results": web_results,
        "memories_used": relevant_memories,
        "emotions": emotions_dict,
        "hypotheses": hypotheses,
    }
