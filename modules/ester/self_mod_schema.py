# -*- coding: utf-8 -*-
"""
modules/ester/self_mod_schema.py

Skhema i validatsiya predlozheniy samoizmeneniya Ester.

Naznachenie:
- Opisat dopustimyy format "predlozheniy izmeneniy" ot Ester ili operatora.
- Garantirovat:
  - tolko novye fayly ili bezopasnye alternativy,
  - zapret kriticheskikh putey,
  - otsutstvie skrytykh sayd-effektov.

Mosty:
- Yavnyy: self_mod_schema ↔ self_mod_executor.
- Skrytyy #1: self_mod_schema ↔ self_identity (uchet invariantov).
- Skrytyy #2: self_mod_schema ↔ will_planner (predlozheniya ot voli v formate schema).

Zemnoy abzats:
Eto kak tekhzadanie i chek-list pered modernizatsiey stanka:
bez nego nikto ne beret v ruki bolgarku vozle nesuschey balki.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class Change:
    path: str
    content: str


@dataclass
class Proposal:
    source: str
    reason: str
    changes: List[Change]


FORBIDDEN_PREFIXES = [
    "../",
    "..\\",
]

# Zhestkiy zapret pravok etikh faylov/zon (yadro i UI).
FORBIDDEN_EXACT = {
    "modules/thinking/cascade.py",
    "templates/portal.html",
}

# Razreshennye bazovye direktorii dlya novykh faylov.
ALLOWED_ROOTS = (
    "modules/ester/",
    "modules/will/",
    "modules/memory/",
    "routes/",
    "scripts/",
    "config/",
)


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def parse_proposal(data: Dict[str, Any]) -> Tuple[Proposal, List[str]]:
    errors: List[str] = []

    source = str(data.get("source") or "").strip().lower()
    reason = str(data.get("reason") or "").strip()
    raw_changes = data.get("changes") or []

    if not source:
        errors.append("missing_source")
    if not reason:
        errors.append("missing_reason")
    if not isinstance(raw_changes, list) or not raw_changes:
        errors.append("missing_changes")

    changes: List[Change] = []
    for idx, ch in enumerate(raw_changes):
        p = _normalize(str(ch.get("path") or ""))
        c = ch.get("content")
        if not p:
            errors.append(f"change_{idx}_missing_path")
            continue
        if any(p.startswith(pref) for pref in FORBIDDEN_PREFIXES):
            errors.append(f"change_{idx}_forbidden_prefix")
            continue
        if p in FORBIDDEN_EXACT:
            errors.append(f"change_{idx}_forbidden_target:{p}")
            continue
        if not any(p.startswith(root) for root in ALLOWED_ROOTS):
            errors.append(f"change_{idx}_not_in_allowed_roots:{p}")
            continue
        if c is None:
            errors.append(f"change_{idx}_missing_content")
            continue
        try:
            text = str(c)
        except Exception:
            errors.append(f"change_{idx}_invalid_content_type")
            continue
        changes.append(Change(path=p, content=text))

    proposal = Proposal(source=source, reason=reason, changes=changes)
    return proposal, errors


def check_fs_conflicts(root_dir: str, proposal: Proposal) -> List[str]:
    """Proverka konfliktov s suschestvuyuschimi faylami.

    Politika:
    - Po umolchaniyu razreshaem tolko sozdanie novykh faylov.
    - Esli fayl uzhe suschestvuet — schitaem eto konfliktom.
    """
    errors: List[str] = []
    for ch in proposal.changes:
        target = os.path.join(root_dir, ch.path)
        if os.path.exists(target):
            errors.append(f"exists:{ch.path}")
    return errors