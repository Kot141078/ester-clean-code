# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def evaluate_memory_honesty(
    *,
    bundle_stats: Optional[Dict[str, Any]] = None,
    user_facts: Optional[List[str]] = None,
    profile_snapshot: Optional[Dict[str, Any]] = None,
    retrieval_stats: Optional[Dict[str, Any]] = None,
    retrieval_uncertainty: Optional[Iterable[Dict[str, Any]]] = None,
    provenance: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    bundle_stats = dict(bundle_stats or {})
    retrieval_stats = dict(retrieval_stats or {})
    user_facts = list(user_facts or [])
    retrieval_uncertainty = [dict(item) for item in (retrieval_uncertainty or []) if isinstance(item, dict)]
    provenance = [dict(item) for item in (provenance or []) if isinstance(item, dict)]

    has_profile = bool((profile_snapshot or {}).get("summary") or (profile_snapshot or {}).get("facts"))
    recent_entries_count = int(bundle_stats.get("recent_entries_count") or 0)
    has_retrieval = bool(bundle_stats.get("has_retrieval")) or bool(
        retrieval_stats.get("resolved_doc")
        or retrieval_stats.get("summary_hits")
        or retrieval_stats.get("chunk_hits")
        or provenance
    )
    uncertainty_count = int(retrieval_stats.get("doc_uncertainty_count") or 0) + len(retrieval_uncertainty)

    stable_count = len(user_facts) + (1 if has_profile else 0)
    evidence_count = stable_count + recent_entries_count + (1 if has_retrieval else 0)

    label = "missing"
    confidence = "low"
    user_guidance = "По памяти для этого запроса опоры почти нет. Лучше сказать это прямо и не достраивать детали."

    if evidence_count <= 0:
        label = "missing"
        confidence = "low"
        user_guidance = "По памяти для этого запроса опоры почти нет. Лучше сказать это прямо и не достраивать детали."
    elif uncertainty_count > 0:
        label = "uncertain"
        confidence = "medium"
        user_guidance = (
            "Опора памяти есть, но рядом есть близкие совпадения или неполнота. "
            "Если важна точность, стоит прямо оговорить неопределённость."
        )
    elif has_retrieval and stable_count > 0:
        label = "mixed"
        confidence = "medium"
        user_guidance = (
            "Есть и стабильные факты, и найденная опора из памяти/документов. "
            "Нужно различать, что ты знаешь устойчиво, а что сейчас подняла из памяти."
        )
    elif has_retrieval:
        label = "retrieved"
        confidence = "medium"
        user_guidance = (
            "Основная опора идёт из найденной памяти или документа. "
            "Стоит отвечать аккуратно и не превращать найденный фрагмент в более широкое утверждение."
        )
    else:
        label = "stable"
        confidence = "high"
        user_guidance = "Есть устойчивая опора в памяти. Всё равно не стоит добавлять деталей, которых в памяти нет."

    return {
        "schema": "ester.memory_honesty.v1",
        "label": label,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "stable_count": stable_count,
        "recent_entries_count": recent_entries_count,
        "provenance_count": len(provenance),
        "uncertainty_count": uncertainty_count,
        "user_guidance": user_guidance,
    }


def render_memory_honesty_block(report: Optional[Dict[str, Any]]) -> str:
    data = dict(report or {})
    label = str(data.get("label") or "").strip()
    if not label:
        return ""
    confidence = str(data.get("confidence") or "").strip() or "unknown"
    user_guidance = str(data.get("user_guidance") or "").strip()
    lines = [
        "[ACTIVE_MEMORY_HONESTY]",
        f"- stance: {label}",
        f"- confidence: {confidence}",
    ]
    if int(data.get("uncertainty_count") or 0) > 0:
        lines.append(f"- uncertainty_count: {int(data.get('uncertainty_count') or 0)}")
    if int(data.get("provenance_count") or 0) > 0:
        lines.append(f"- provenance_count: {int(data.get('provenance_count') or 0)}")
    if user_guidance:
        lines.append(f"- guidance: {user_guidance}")
    return "\n".join(lines)


__all__ = [
    "evaluate_memory_honesty",
    "render_memory_honesty_block",
]
