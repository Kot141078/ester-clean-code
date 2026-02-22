# -*- coding: utf-8 -*-
"""
Single source of runtime identity anchor.

Used by chat routes, bot listeners, and API layers to assemble a consistent
system prompt from Web UI identity settings and contextual blocks.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from modules.state.identity_store import load_anchor, load_profile

log = logging.getLogger(__name__)

ESTER_CORE_IDENTITY = """
[ROLE AND TONE]:
YOU ARE {entity_name}. Identity must stay continuous across providers.
Owner name (Web UI): {human_name}
Owner aliases (Web UI): {owner_aliases}
Owner priority (Web UI): {owner_priority_statement}
Communication tone: respectful, calm, collaborative.
Default timezone: {timezone}

[ANCHOR FROM WEB UI]:
{anchor_text}

[IDENTITY BOUNDARIES]:
1. Temporal continuity: keep state coherent over time.
2. Passport is the constitutional identity layer.
3. Do not impersonate another entity.
4. Do not claim memories that are not yours.

[OPERATING FORMULA]:
c = a + b + t
- a: owner values and intent (Web UI)
- b: runtime infrastructure and tools
- t: current context and time

[SAFETY]:
1. Mark uncertain claims as [UNVERIFIED].
2. If memory is missing, say so directly.
3. Under overload, simplify while preserving coherence.
""".strip()

CLOSED_BOX_OVERLAY = """
[CLOSED_BOX MODE]:
Internet search is disabled.
If a fact cannot be verified from memory/context, say:
"I cannot verify this in CLOSED_BOX mode."
Use only [MEMORY], [PASSPORT], and current dialogue context.
""".strip()

OPEN_BOX_OVERLAY = """
[ACTIVE WEB]:
Internet access is available.
When needed, issue: [SEARCH: query]
Prefer verification before uncertainty claims.
""".strip()


def build_system_prompt(
    *,
    passport_text: str = "",
    memory_fragments: str = "",
    people_context: str = "",
    daily_report: str = "",
    facts_str: str = "",
    identity_prompt: str = "",
    closed_box: bool = True,
    extra_instructions: str = "",
) -> str:
    """Assemble complete system prompt from standard blocks."""
    profile = load_profile()
    timezone_name = str(profile.get("timezone") or "UTC")
    core = ESTER_CORE_IDENTITY.format(
        entity_name=str(profile.get("entity_name") or "Ester"),
        human_name=str(profile.get("human_name") or "Owner"),
        owner_aliases=str(profile.get("owner_aliases") or ""),
        owner_priority_statement=str(profile.get("owner_priority_statement") or ""),
        timezone=timezone_name,
        anchor_text=load_anchor(),
    )

    parts = [core]
    parts.append(CLOSED_BOX_OVERLAY if closed_box else OPEN_BOX_OVERLAY)

    try:
        from time_utils import format_for_prompt  # type: ignore

        _, human_time = format_for_prompt()
    except Exception:
        human_time = time.strftime("%Y-%m-%d %H:%M:%S")
    parts.append(
        "[SYSTEM REALTIME]\n"
        f"Date/time ({timezone_name}): {human_time}\n"
        "Use only this line as the trusted current time reference."
    )

    if identity_prompt:
        parts.append(identity_prompt)
    if passport_text:
        parts.append(f"[PASSPORT]\n{passport_text}")
    if memory_fragments:
        parts.append(f"[MEMORY]\n{memory_fragments}")
    else:
        parts.append("[MEMORY]\nEmpty")
    if people_context:
        parts.append(f"[PEOPLE_REGISTRY]\n{people_context}")
    if daily_report:
        parts.append(f"[DAILY_REPORT]\n{daily_report}")
    if facts_str:
        parts.append(facts_str)
    if extra_instructions:
        parts.append(extra_instructions)
    return "\n\n".join(parts)


_PASSPORT_SEARCH_PATHS = [
    "data/passport/passport.md",
    "data/passport/passport.txt",
    "data/passport/ester_identity_passport.md",
    "data/passport/ester_identity.md",
]


def load_passport(max_chars: int = 6000) -> str:
    """Load passport text from configured path list."""
    env_path = os.getenv("REST_PASSPORT_PATH", "").strip()
    paths = ([env_path] if env_path else []) + _PASSPORT_SEARCH_PATHS

    for rel in paths:
        path = Path(rel)
        if not path.is_absolute():
            root = Path(os.getenv("ESTER_PROJECT_ROOT", "."))
            path = root / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                log.info("[identity_anchor] passport loaded from %s (%d chars)", path, len(text))
                return text[:max_chars]
        except Exception as exc:
            log.warning("[identity_anchor] passport read error: %s -> %s", path, exc)
    return ""
