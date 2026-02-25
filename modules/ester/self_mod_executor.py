# -*- coding: utf-8 -*-
"""modules/ester/self_mod_executor.py

Ispolnitel bezopasnykh predlozheniy samoizmeneniya Ester.

Name:
- Prinimat strukturirovannye predlozheniya (iz self_mod_schema).
- V rezhime A (ESTER_SELF_MOD_AB=A) rabotat kak dry-run: tolko pokazyvat, what moglo by byt.
- V rezhime B (ESTER_SELF_MOD_AB=B) primenyat dopustimye izmeneniya:
  - sozdavat novye fayly v razreshennykh zonakh;
  - bez pravki kriticheskikh faylov;
  - bez skrytykh demonov.

Soglasie:
- Varianty:
  - source == "operator" — schitat odobrennym Owner.
  - source == "ester" i ESTER_SELF_MOD_ALLOW_ESTER=1 — schitat vyrazhennoy voley Ester.
  - inache - ne primenyat, tolko otchet.

Mosty:
- Yavnyy: self_mod_executor ↔ volya/Ester (source/allow).
- Skrytyy #1: self_mod_executor ↔ faylovaya sistema (no tolko v yavnom rezhime B).
- Skrytyy #2: self_mod_executor ↔ chelovek-operator (ponyatnyy otchet o izmeneniyakh).

Zemnoy abzats:
Eto kak masterskaya, kuda dopuskayut tolko s naryadom:
mozhno prikrutit novuyu panel, no nesuschie steny ne trogaem."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from . import self_mod_schema as schema  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _mode() -> str:
    return (os.getenv("ESTER_SELF_MOD_AB") or "A").strip().upper() or "A"


def _allow_ester() -> bool:
    v = (os.getenv("ESTER_SELF_MOD_ALLOW_ESTER") or "0").strip()
    return v in ("1", "true", "True")


def _has_consent(source: str) -> bool:
    if source == "operator":
        return True
    if source == "ester" and _allow_ester():
        return True
    return False


def apply(root_dir: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point.

    root_dir - the root of the project (usually the one where app.po is).

    Returns the JSION report:
    ZZF0Z"""
    mode = _mode()
    proposal, errors = schema.parse_proposal(data)

    fs_conflicts = schema.check_fs_conflicts(root_dir, proposal)
    errors.extend(fs_conflicts)

    if not proposal.changes:
        errors.append("no_valid_changes")

    consent = _has_consent(proposal.source)

    report_changes: List[Dict[str, Any]] = [
        {
            "path": ch.path,
            "size": len(ch.content),
        }
        for ch in proposal.changes
    ]

    if errors:
        return {
            "ok": False,
            "mode": mode,
            "applied": False,
            "changes": report_changes,
            "errors": errors,
            "note": "proposal_invalid",
        }

    # Mode A - only dry runes.
    if mode != "B":
        note = "dry_run_only"
        if not consent:
            note = "dry_run_only_no_consent"
        return {
            "ok": True,
            "mode": mode,
            "applied": False,
            "changes": report_changes,
            "errors": [],
            "note": note,
        }

    # Mode B - we can use it, but only with consent.
    if not consent:
        return {
            "ok": False,
            "mode": mode,
            "applied": False,
            "changes": report_changes,
            "errors": ["no_consent"],
            "note": "self_mod_blocked",
        }

    # Primenyaem: sozdaem novye fayly.
    for ch in proposal.changes:
        target = os.path.join(root_dir, ch.path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(ch.content)

    return {
        "ok": True,
        "mode": mode,
        "applied": True,
        "changes": report_changes,
        "errors": [],
        "note": "changes_applied",
    }