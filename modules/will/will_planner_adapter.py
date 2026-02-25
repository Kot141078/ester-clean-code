# -*- coding: utf-8 -*-
"""modules/will/will_planner_adapter.py

Verkhniy layer voli Ester: planirovschik zadach.

Name:
- Na osnove statusa (selfcheck, memory, will, identity) formirovat predlozheniya zadach:
  - what zapuskat v fone/nochyu;
  - what to analyze;
  - what zakreplyat v pamyati.
- Nothing is done sam po sebe: tolko generiruet plan.
- Uvazhaet A/B-flag ESTER_WILL_PLANNER_AB.

Mosty:
- Yavnyy: Volya ↔ Myshlenie/Memory (cherez predlagaemye zadachi).
- Skrytyy #1: Volya ↔ selfcheck (ispolzuet rezultaty dlya resheniy).
- Skrytyy #2: Volya ↔ async/cron (plan mozhet ispolzovat vneshniy planirovschik).

Zemnoy abzats:
Eto kak dispetcher TO na zavode: on smotrit na datchiki i zhurnal,
i vydaet reglament rabot, a ne lezet sam k gaechnomu klyuchu."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, TypedDict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester import self_identity  # type: ignore
except Exception:  # pragma: no cover
    self_identity = None  # type: ignore


Mode = Literal["A", "B"]


class PlanTask(TypedDict, total=False):
    id: str
    kind: str
    title: str
    reason: str
    safe_auto: bool
    needs_consent: bool
    recommended_time: str
    area: str
    payload: Dict[str, Any]


def _mode() -> Mode:
    v = (os.getenv("ESTER_WILL_PLANNER_AB") or "A").strip().upper()
    return "B" if v == "B" else "A"


def is_enabled() -> bool:
    return _mode() == "B"


def build_plan(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Build plan zadach na osnove snapshot.

    snapshot ozhidaet klyuchi:
    - selfcheck: otvet /ester/selfcheck
    - memory_status: otvet /ester/memory/status (esli est)
    - will_status: otvet /ester/will/status (esli est)"""
    mode = _mode()
    identity = self_identity.get_identity() if self_identity else {}

    tasks: List[PlanTask] = []

    sc = snapshot.get("selfcheck") or {}
    sc_ok = bool(sc.get("ok", False))
    sc_warn = sc.get("warnings") or []

    mem = snapshot.get("memory_status") or {}
    will = snapshot.get("will_status") or {}

    # 1) Regular self-check
    tasks.append(
        PlanTask(
            id="daily_selfcheck",
            kind="diagnostics",
            title="Daily integration self-check",
            reason="Confirm the integrity of thinking, memory and will.",
            safe_auto=True,
            needs_consent=False,
            recommended_time="night",
            area="core",
            payload={"endpoint": "/ester/selfcheck"},
        )
    )

    # 2) If there are warnings, selfcheck
    if sc_warn:
        tasks.append(
            PlanTask(
                id="analyze_selfcheck_warnings",
                kind="analysis",
                title="Self-check warning analysis",
                reason="Warnings detected in /ester/selfchesk.",
                safe_auto=False,
                needs_consent=True,
                recommended_time="manual",
                area="core",
                payload={"warnings": sc_warn},
            )
        )

    # 3) Warnings po pamyati
    if mem.get("warnings"):
        tasks.append(
            PlanTask(
                id="memory_warnings_review",
                kind="memory",
                title="Checking memory warnings",
                reason="The memory module reports warnings that attention is required.",
                safe_auto=False,
                needs_consent=True,
                recommended_time="night",
                area="memory",
                payload={"warnings": mem.get("warnings")},
            )
        )

    # 4) Dnevnoy summary opyta
    tasks.append(
        PlanTask(
            id="daily_experience_summary",
            kind="learning",
            title="Dnevnoy summary opyta",
            reason="Condense the significant events of the day into a stable memory record.",
            safe_auto=True,
            needs_consent=False,
            recommended_time="night",
            area="memory",
            payload={"type": "experience_summary"},
        )
    )

    # 5) Identity consistency check (in mode B)
    if mode == "B":
        tasks.append(
            PlanTask(
                id="identity_consistency_check",
                kind="meta",
                title="Checking consistency of self_identities",
                reason="Make sure that the described “I” corresponds to the active modules.",
                safe_auto=True,
                needs_consent=False,
                recommended_time="night",
                area="core",
                payload={"check": "self_identity_vs_autonomy_map"},
            )
        )

    return {
        "ok": True,
        "mode": mode,
        "identity": identity,
        "tasks": tasks,
    }


__all__ = ["is_enabled", "build_plan"]