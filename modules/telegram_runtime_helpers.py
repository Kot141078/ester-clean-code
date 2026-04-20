# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Mapping


def passport_record_to_short_term_messages(rec: Mapping[str, Any] | None) -> List[Dict[str, str]]:
    """
    Normalize legacy passport dialog rows into short-term messages.

    Historically both schemas existed in JSONL:
    - role_user / role_assistant
    - user / assistant
    """
    src = rec if isinstance(rec, Mapping) else {}
    out: List[Dict[str, str]] = []
    for key, role in (
        ("role_user", "user"),
        ("user", "user"),
        ("role_assistant", "assistant"),
        ("assistant", "assistant"),
    ):
        val = src.get(key)
        text = str(val or "").strip()
        if text:
            out.append({"role": role, "content": text})
    return out


def document_delivery_failure_notice(orig_name: str = "") -> str:
    name = str(orig_name or "").strip()
    if name:
        return (
            f"Ответ по файлу {name} уже подготовила, но не смогла доставить его в Telegram "
            f"из-за таймаута или сетевой ошибки."
        )
    return "Ответ по файлу уже подготовила, но не смогла доставить его в Telegram из-за таймаута или сетевой ошибки."


__all__ = [
    "passport_record_to_short_term_messages",
    "document_delivery_failure_notice",
]

