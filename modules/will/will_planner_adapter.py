# -*- coding: utf-8 -*-
"""
modules/will/will_planner_adapter.py

Verkhniy sloy voli Ester: planirovschik zadach.

Naznachenie:
- Na osnove statusa (selfcheck, memory, will, identity) formirovat predlozheniya zadach:
  - chto zapuskat v fone/nochyu;
  - chto analizirovat;
  - chto zakreplyat v pamyati.
- Nichego ne ispolnyaet sam po sebe: tolko generiruet plan.
- Uvazhaet A/B-flag ESTER_WILL_PLANNER_AB.

Mosty:
- Yavnyy: Volya ↔ Myshlenie/Memory (cherez predlagaemye zadachi).
- Skrytyy #1: Volya ↔ selfcheck (ispolzuet rezultaty dlya resheniy).
- Skrytyy #2: Volya ↔ async/cron (plan mozhet ispolzovat vneshniy planirovschik).

Zemnoy abzats:
Eto kak dispetcher TO na zavode: on smotrit na datchiki i zhurnal,
i vydaet reglament rabot, a ne lezet sam k gaechnomu klyuchu.
"""

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
    """Stroit plan zadach na osnove snapshot.

    snapshot ozhidaet klyuchi:
    - selfcheck: otvet /ester/selfcheck
    - memory_status: otvet /ester/memory/status (esli est)
    - will_status: otvet /ester/will/status (esli est)
    """
    mode = _mode()
    identity = self_identity.get_identity() if self_identity else {}

    tasks: List[PlanTask] = []

    sc = snapshot.get("selfcheck") or {}
    sc_ok = bool(sc.get("ok", False))
    sc_warn = sc.get("warnings") or []

    mem = snapshot.get("memory_status") or {}
    will = snapshot.get("will_status") or {}

    # 1) Regulyarnyy selfcheck
    tasks.append(
        PlanTask(
            id="daily_selfcheck",
            kind="diagnostics",
            title="Ezhednevnyy integratsionnyy self-check",
            reason="Podtverdit tselostnost myshleniya, pamyati i voli.",
            safe_auto=True,
            needs_consent=False,
            recommended_time="night",
            area="core",
            payload={"endpoint": "/ester/selfcheck"},
        )
    )

    # 2) Esli est preduprezhdeniya selfcheck
    if sc_warn:
        tasks.append(
            PlanTask(
                id="analyze_selfcheck_warnings",
                kind="analysis",
                title="Analiz preduprezhdeniy self-check",
                reason="Vyyavleny preduprezhdeniya v /ester/selfcheck.",
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
                title="Proverka preduprezhdeniy pamyati",
                reason="Modul pamyati soobschaet warnings, trebuetsya vnimanie.",
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
            reason="Szhat znachimye sobytiya dnya v ustoychivuyu zapis pamyati.",
            safe_auto=True,
            needs_consent=False,
            recommended_time="night",
            area="memory",
            payload={"type": "experience_summary"},
        )
    )

    # 5) Proverka soglasovannosti identichnosti (v rezhime B)
    if mode == "B":
        tasks.append(
            PlanTask(
                id="identity_consistency_check",
                kind="meta",
                title="Proverka soglasovannosti self_identity",
                reason="Ubeditsya, chto opisannoe «Ya» sootvetstvuet aktivnym modulyam.",
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