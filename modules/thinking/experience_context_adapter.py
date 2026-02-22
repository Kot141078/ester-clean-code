# -*- coding: utf-8 -*-
"""
modules/thinking/experience_context_adapter.py — adapter sloya opyta dlya kaskada myshleniya.

Zadacha:
  - Dat kaskadu myshleniya prostoy, stabilnyy sposob poluchit "kontekst opyta" Ester.
  - Ispolzovat tolko publichnyy API modules.memory.experience.*
  - Ne menyat cascade.py i ne navyazyvat integratsiyu — tolko optsionalnyy most.

MOSTY:
- Yavnyy: (modules.memory.experience ↔ modules.thinking.*) — opyt stanovitsya dostupen myshleniyu.
- Skrytyy #1: (anchors/insights ↔ prompt/context) — agregirovannye opory upakovyvayutsya v kompaktnyy tekst.
- Skrytyy #2: (A/B ↔ povedenie) — mozhno po ENV upravlyat, kogda i kak opyt podtyagivat.

ZEMNOY ABZATs:
Inzhenerno eto utilita formata "prepare_context()":
kaskad ili lyuboy verkhniy sloy mozhet sprosit odin raz i poluchit tekstovyy blok
s vyzhimkoy opyta vmesto togo, chtoby rukami lazit v pamyat.

# c=a+b
"""
from __future__ import annotations

from typing import Dict, Any
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import experience  # type: ignore
except Exception:
    experience = None  # type: ignore


ENABLED_ENV = "ESTER_THINKING_EXPERIENCE"
MAX_CHARS_ENV = "ESTER_THINKING_EXPERIENCE_MAX_CHARS"


def _bool_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on", "b")


def _max_chars(default: int = 1200) -> int:
    raw = os.getenv(MAX_CHARS_ENV)
    if not raw:
        return default
    try:
        v = int(raw)
        return max(200, min(v, 4000))
    except ValueError:
        return default


def get_experience_context() -> str:
    """
    Vozvraschaet kompaktnyy tekstovyy blok s opytom Ester.

    Garantii:
      - Nikogda ne brosaet isklyucheniya naruzhu.
      - Pri otklyuchenii ili otsutstvii modulya experience vozvraschaet "".
      - Format: chelovekochitaemyy, gotov dlya vklyucheniya v prompt / kontekst.
    """
    if not _bool_env(ENABLED_ENV, default=True):
        return ""

    if experience is None:
        return ""

    try:
        profile: Dict[str, Any] = experience.build_experience_profile()  # type: ignore[attr-defined]
    except Exception:
        return ""

    if not isinstance(profile, dict) or not profile.get("ok"):
        return ""

    top_terms = profile.get("top_terms") or []
    sample = profile.get("sample") or []
    if not top_terms and not sample:
        return ""

    lines = []
    lines.append("Opornyy opyt Ester (avto-vyzhimka):")

    if top_terms:
        terms_str = ", ".join(str(t) for t in top_terms[:12])
        lines.append(f"- klyuchevye motivy: {terms_str}")

    if sample:
        lines.append("- primery insaytov:")
        for item in sample[:3]:
            title = (item.get("title") or "").strip()
            text = (item.get("text") or "").strip()
            if title and text:
                lines.append(f"  • {title}: {text}")
            elif text:
                lines.append(f"  • {text}")
            elif title:
                lines.append(f"  • {title}")

    text = "\n".join(lines).strip()
    max_len = _max_chars()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"

    return text