# -*- coding: utf-8 -*-
"""tests/synergy/test_learning.py - proverki obucheniya i runtime-patcha.

MOSTY:
- (Yavnyy) Obnovlyaem vesa po sobytiyam (Planned→OutcomeReported), proveryaem EMA-sdvig.
- (Skrytyy #1) Patchim fit_roles_ext i ubezhdaemsya, chto skora korrektiruyutsya.
- (Skrytyy #2) Demonstriruem “uluchshenie” sinteticheskogo vybora platformy after obucheniya.

ZEMNOY ABZATs:
Esli eti testy zelenye - bazovyy “uchebnyy kontur” zhiv: signaly lovyatsya, vesa menyayutsya, planirovaniya uchityvayut opyt.

# c=a+b"""
from __future__ import annotations

import os
import time

import pytest

from modules.synergy.store import AssignmentStore
from modules.synergy.learning import LearningManager, enable_runtime_patch
from modules.synergy.state_store import STORE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ester.db"
    monkeypatch.setenv("SYNERGY_DB_PATH", str(db_path))
    # chistyy STORE
    STORE._agents.clear(); STORE._teams.clear()
    yield
    STORE._agents.clear(); STORE._teams.clear()

def _seed_equal_platforms():
    # Two drones with the same basic profile - so that the patch is visible
    STORE.upsert_agent({"id":"device.slow","kind":"device","profile":{"name":"Slow","device":"drone","flight_time_min":20,"payload_g":200,"latency_ms":200}})
    STORE.upsert_agent({"id":"device.fast","kind":"device","profile":{"name":"Fast","device":"drone","flight_time_min":20,"payload_g":200,"latency_ms":200}})
    STORE.upsert_agent({"id":"human.strat","kind":"human","profile":{"name":"Strateg","age":60,"exp_years":35,"domains":["taktika"]}})
    STORE.upsert_agent({"id":"human.op","kind":"human","profile":{"name":"Operator","age":24,"exp_years":3,"domains":["upravlenie"]}})
    STORE.create_team("Recon L","aerorazvedka",["strategist","operator","platform"])

def test_weights_update_from_events_success_and_failure(monkeypatch):
    _seed_equal_platforms()
    s = AssignmentStore.default()
    lm = LearningManager.default()

    # Synthetic plan: assigned words as a platform
    assigned = {"platform":"device.slow","operator":"human.op","strategist":"human.strat"}
    res = {"assigned":assigned, "trace_id":"T1", "total":1.0, "penalty":0.0}
    s.hook_assign_result("Recon L", res, request_id="RID-L2")
    s.hook_outcome("Recon L", "success", request_id="RID-L2")

    # Obnovim vesa → slow/platform dolzhen poluchit bonus > 1.0
    upd = lm.train_from_events(team_id="Recon L")
    assert upd >= 1
    w = lm.get_weight("device.slow","platform")
    assert w > 1.0

    # Now let’s fail the fast/platforms and make sure that the entire fast is < 1.0
    res2 = {"assigned":{"platform":"device.fast","operator":"human.op","strategist":"human.strat"},"trace_id":"T2","total":1.0,"penalty":0.0}
    s.hook_assign_result("Recon L", res2, request_id="RID-L3")
    s.hook_outcome("Recon L", "failure", request_id="RID-L3")
    lm.train_from_events(team_id="Recon L")
    w2 = lm.get_weight("device.fast","platform")
    assert w2 < 1.0

def test_runtime_patch_affects_scores(monkeypatch):
    _seed_equal_platforms()
    # Mute role_model.fit_roles_is to return the same speeds
    import modules.synergy.role_model as rm
    def fake_fit(agent):
        # all roles are 0.5 so that the multiplier is visible
        return {"platform":0.5,"operator":0.5,"strategist":0.5}
    rm.fit_roles_ext = fake_fit

    lm = LearningManager.default()
    lm.set_weight("device.fast","platform",1.25)  # obuchennyy bonus
    enable_runtime_patch()

    # Before the patch, fake_fit would have returned 0.5, after the patch it would have been multiplied by 1.25 and trimmed to 1.0
    a_fast = {"id":"device.fast"}
    sc = rm.fit_roles_ext(a_fast)
    assert pytest.approx(sc["platform"], rel=1e-6) == min(1.0, 0.5 * 1.25)

def test_synthetic_plan_improves_with_learned_weights(monkeypatch):
    _seed_equal_platforms()
    # Let's keep the different weights so that "fast" becomes preferable in the platform
    lm = LearningManager.default()
    lm.set_weight("device.fast","platform",1.20)
    lm.set_weight("device.slow","platform",0.90)

    import modules.synergy.role_model as rm
    # The base is the same - 0.6, without training the platform is selected randomly/in order
    def fake_fit(agent):
        return {"platform":0.6,"operator":0.6,"strategist":0.6}
    rm.fit_roles_ext = fake_fit
    enable_runtime_patch()

    # Sravnim skora posle patcha
    sc_fast = rm.fit_roles_ext({"id":"device.fast"})
    sc_slow = rm.fit_roles_ext({"id":"device.slow"})
    assert sc_fast["platform"] > sc_slow["platform"]