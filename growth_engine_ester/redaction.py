# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any

from growth_engine.common import err, ok

SECRET_RE = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+\S+|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+|secret\s*[:=]\s*\S+|token\s*[:=]\s*\S+|begin\s+[a-z0-9 ]*private\s+key)"
)
PRIVATE_DUMP_RE = re.compile(r"(?i)(raw_private_payload|memory_dump|vector_dump|full_chat_log|private_conversation)")
MAX_NOTE_CHARS = 500
MAX_SOURCE_REF_CHARS = 240


def compact_text(value: Any, *, limit: int) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())[: int(limit)]


def validate_safe_text(value: Any, *, field: str, limit: int) -> dict[str, Any]:
    text = compact_text(value, limit=limit + 1)
    if len(text) > int(limit):
        return err("SRLM_TEXT_TOO_LONG", f"{field} exceeds {limit} chars", field=field)
    if SECRET_RE.search(text):
        return err("SRLM_SECRET_REJECTED", f"{field} contains secret-like material", field=field)
    if PRIVATE_DUMP_RE.search(text):
        return err("SRLM_PRIVATE_PAYLOAD_REJECTED", f"{field} contains private payload marker", field=field)
    return ok(text=text, redacted=True)


def redacted_note(value: Any) -> dict[str, Any]:
    return validate_safe_text(value, field="notes", limit=MAX_NOTE_CHARS)


def redacted_source_ref(value: Any) -> dict[str, Any]:
    return validate_safe_text(value, field="source_ref", limit=MAX_SOURCE_REF_CHARS)
