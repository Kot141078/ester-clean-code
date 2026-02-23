# -*- coding: utf-8 -*-
"""
tests/synergy/test_properties.py — property-based testy orkestratora.

MOSTY:
- (Yavnyy) Generiruem sluchaynye komandy i nabory agentov; proveryaem bazovye invarianty naznacheniya.
- (Skrytyy #1) Podderzhka overrides — sluchayno fiksiruem 0..2 roley i ubezhdaemsya v soblyudenii fiksa.
- (Skrytyy #2) Idempotentnost assign_v2 po request_id na odnom i tom zhe vkhode.

ZEMNOY ABZATs:
Daet uverennost, chto kakie by «sostavy» ni prishli, plan validen: vse trebuemye roli naznacheny, shtrafy ne ukhodyat v nekorrektnye znacheniya, a fiksy soblyudayutsya.

# c=a+b
"""
from __future__ import annotations

import os
import random
import string

import pytest

try:
    from hypothesis import given, strategies as st, settings
except Exception:
    pytest.skip("hypothesis is not installed; skip property tests", allow_module_level=True)

from modules.synergy.state_store import STORE
from modules.synergy.orchestrator_v2 import assign_v2
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROLES = ["strategist","operator","platform","communicator","observer","mentor","backup","qa"]

def _rand_id(prefix: str) -> str:
    return f"{prefix}." + "".join(random.choice(string.ascii_lowercase) for _ in range(6))

def _mk_agent(kind: str) -> dict:
    if kind == "human":
        return {
            "id": _rand_id("human"),
            "kind": "human",
            "profile": {
                "name": "H",
                "age": random.randint(18, 70),
                "exp_years": random.randint(0, 40),
                "domains": random.sample(["aerorazvedka","taktika","upravlenie","mekhanika","svyaz"], k=random.randint(1,3))
            }
        }
    return {
        "id": _rand_id("device"),
        "kind": "device",
        "profile": {
            "name": "D",
            "device": random.choice(["drone","ugv","arm"]),
            "flight_time_min": random.randint(8, 40),
            "payload_g": random.randint(50, 800),
            "latency_ms": random.randint(10, 800)
        }
    }

@settings(max_examples=25, deadline=None)
@given(
    n_h=st.integers(min_value=2, max_value=6),
    n_d=st.integers(min_value=1, max_value=4),
    roles_cnt=st.integers(min_value=2, max_value=5)
)
def test_assign_invariants(n_h, n_d, roles_cnt, monkeypatch):
    # Chistyy STORE
    STORE._agents.clear(); STORE._teams.clear()

    # Sgeneriruem agentov
    agents = [ _mk_agent("human") for _ in range(n_h) ] + [ _mk_agent("device") for _ in range(n_d) ]
    for a in agents:
        STORE.upsert_agent(a)

    # Komanda i roli
    team_id = "T-"+_rand_id("team")
    roles = random.sample(ROLES, k=roles_cnt)
    STORE.create_team(team_id, "raznoe", roles)

    # overrides
    overrides = {}
    if random.random() < 0.7:
        # zafiksiruem 0..2 roley khumanami/devaysami iz pula
        for r in random.sample(roles, k=random.randint(0, min(2,len(roles)))):
            overrides[r] = random.choice(agents)["id"]

    # Naznachenie
    res = assign_v2(team_id, overrides=overrides, request_id="RID-PROP")
    assert res.get("ok") is True
    assigned = res.get("assigned") or {}

    # Invarianty:
    # 1) Vse trebuemye roli prisutstvuyut
    assert set(roles).issubset(set(assigned.keys()))
    # 2) Kazhdaya naznachennaya suschnost suschestvuet sredi agentov
    ids = set(a["id"] for a in agents)
    for r, aid in assigned.items():
        assert aid in ids
    # 3) Shtraf/total — konechnye chisla
    tot = float(res.get("total") or 0.0)
    pen = float(res.get("penalty") or 0.0)
    assert tot >= 0.0
    assert pen >= 0.0
    # 4) overrides soblyudeny
    for r, aid in overrides.items():
        assert assigned.get(r) == aid

    # 5) Idempotentnost
    res2 = assign_v2(team_id, overrides=overrides, request_id="RID-PROP")
    assert res2.get("trace_id") == res.get("trace_id")