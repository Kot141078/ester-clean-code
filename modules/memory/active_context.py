# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

try:
    from modules.rag.retrieval_router import _is_internal_flashback_record as _router_internal_flashback_record  # type: ignore
except Exception:
    _router_internal_flashback_record = None  # type: ignore


def _trim_text(text: str, max_chars: int) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _format_list_section(title: str, items: Iterable[str], *, max_items: int, max_item_chars: int) -> str:
    lines: List[str] = []
    for item in items:
        clean = _normalize_text(item)
        if not clean:
            continue
        lines.append(f"- {_trim_text(clean, max_item_chars)}")
        if len(lines) >= max_items:
            break
    if not lines:
        return ""
    return f"[{title}]\n" + "\n".join(lines)


def _format_recent_entries(entries: Iterable[Dict[str, Any]], *, max_items: int, max_item_chars: int) -> str:
    lines: List[str] = []
    for row in entries or []:
        if not isinstance(row, dict):
            continue
        if callable(_router_internal_flashback_record):
            try:
                if _router_internal_flashback_record(row):
                    continue
            except Exception:
                pass
        text = _normalize_text(row.get("text") or "")
        if not text:
            continue
        kind = str(row.get("type") or row.get("kind") or "").strip().lower() or "fact"
        lines.append(f"- ({kind}) {_trim_text(text, max_item_chars)}")
        if len(lines) >= max_items:
            break
    if not lines:
        return ""
    return "[ACTIVE_RECENT_FACTS]\n" + "\n".join(lines)


def build_active_memory_bundle(
    *,
    user_text: str,
    evidence_memory: str,
    user_facts: Optional[List[str]] = None,
    recent_entries: Optional[List[Dict[str, Any]]] = None,
    profile_context: str = "",
    honesty_block: str = "",
    recent_doc_context: str = "",
    people_context: str = "",
    daily_report: str = "",
    max_context_chars: int = 25000,
) -> Dict[str, Any]:
    user_facts = list(user_facts or [])
    recent_entries = list(recent_entries or [])

    sections: List[str] = []

    profile_block = ""
    profile_clean = _trim_text(profile_context, 2600)
    if profile_clean:
        profile_block = profile_clean
        sections.append(profile_block)

    honesty_section = ""
    honesty_clean = _trim_text(honesty_block, 1800)
    if honesty_clean:
        honesty_section = honesty_clean
        sections.append(honesty_section)

    facts_block = _format_list_section(
        "ACTIVE_USER_FACTS",
        user_facts,
        max_items=8,
        max_item_chars=220,
    )
    if facts_block:
        sections.append(facts_block)

    recent_facts_block = _format_recent_entries(
        recent_entries,
        max_items=6,
        max_item_chars=220,
    )
    if recent_facts_block:
        sections.append(recent_facts_block)

    recent_doc_block = ""
    recent_doc_clean = _trim_text(recent_doc_context, 3200)
    if recent_doc_clean:
        recent_doc_block = f"[ACTIVE_RECENT_DOCUMENT]\n{recent_doc_clean}"
        sections.append(recent_doc_block)

    retrieval_block = ""
    retrieval_clean = _trim_text(evidence_memory, 12000)
    if retrieval_clean:
        retrieval_block = f"[ACTIVE_RECALL]\n{retrieval_clean}"
        sections.append(retrieval_block)

    people_block = ""
    people_clean = _trim_text(people_context, 1800)
    if people_clean and people_clean.lower() != "n/a":
        people_block = f"[ACTIVE_PEOPLE]\n{people_clean}"
        sections.append(people_block)

    daily_block = ""
    daily_clean = _trim_text(daily_report, 2600)
    if daily_clean:
        daily_block = f"[ACTIVE_DAILY]\n{daily_clean}"
        sections.append(daily_block)

    if sections:
        memory_stance = (
            "[ACTIVE_MEMORY_STANCE]\n"
            "Используй только подтвержденные элементы из активной памяти ниже. "
            "Если этого недостаточно, скажи честно, что в памяти нет нужной детали."
        )
    else:
        memory_stance = (
            "[ACTIVE_MEMORY_STANCE]\n"
            "Релевантная активная память для этого запроса не найдена. "
            "Опирайся на текущее сообщение и не придумывай прошлые события."
        )
    sections.append(memory_stance)

    context = "\n\n".join(part for part in sections if part).strip()
    context = _trim_text(context, max_context_chars)

    return {
        "schema": "ester.active_memory.v1",
        "query": _trim_text(user_text, 500),
        "context": context,
        "profile_block": profile_block,
        "honesty_block": honesty_section,
        "facts_block": facts_block,
        "recent_facts_block": recent_facts_block,
        "recent_doc_block": recent_doc_block,
        "retrieval_block": retrieval_block,
        "people_block": people_block,
        "daily_block": daily_block,
        "memory_stance": memory_stance,
        "stats": {
            "has_profile": bool(profile_clean),
            "has_honesty": bool(honesty_clean),
            "facts_count": len(user_facts),
            "recent_entries_count": len(recent_entries),
            "has_recent_doc": bool(recent_doc_clean),
            "has_retrieval": bool(retrieval_clean),
            "has_people": bool(people_block),
            "has_daily": bool(daily_block),
            "context_chars": len(context),
            "sections_count": len([part for part in sections if part]),
        },
    }


__all__ = ["build_active_memory_bundle"]
