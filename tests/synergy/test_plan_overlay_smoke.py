# -*- coding: utf-8 -*-
"""
tests/synergy/test_plan_overlay_smoke.py — dymovoy test: overley schitaet bias/synergy i ne izmenyaet plan.

MOSTY:
- (Yavnyy) Proveryaem build_overlay(...), chto vydaet metadannye dlya kandidatov.
- (Skrytyy #1) Plan ostaetsya netronutym (id/score na meste).
- (Skrytyy #2) Rabotaet dazhe esli extras.pairwise pust — synergy_avg=0.

ZEMNOY ABZATs:
Mini-garantiya: podsvetka bezopasna — tolko metadannye, ni odnogo izmeneniya v resheniyakh.

# c=a+b
"""
from __future__ import annotations

from modules.synergy.plan_overlay import build_overlay
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_plan_overlay_smoke():
    plan = {"steps":[{"role":"pilot","candidates":[{"agent_id":"pilot-1","score":0.6},{"agent_id":"pilot-2","score":0.5}]}],
            "team":["coordinator-7"]}
    extras = {"advice":[{"agent_id":"pilot-1","normalized":0.8,"labels":["pilot"],"why":["ok"]},
                        {"agent_id":"pilot-2","normalized":0.4,"labels":["novice"],"why":["meh"]}],
              "team_bonus":0.12,"pairwise":{}}
    ov = build_overlay(plan, extras, alpha=0.2)
    assert "candidates" in ov and "pilot-1" in ov["candidates"]
    assert ov["candidates"]["pilot-1"]["advice_bias"] > 0
    assert ov["candidates"]["pilot-2"]["advice_bias"] < 0
    # plan ne menyaetsya
    assert plan["steps"][0]["candidates"][0]["agent_id"] == "pilot-1"