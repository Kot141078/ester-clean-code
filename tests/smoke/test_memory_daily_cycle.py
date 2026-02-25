# -*- coding: utf-8 -*-
"""tests/smoke/test_memory_daily_cycle.py

Bystryy smoke-test dlya modules.memory.daily_cycle:
- importiruetsya bez oshibok;
- run_cycle() vozvraschaet dict s bazovymi polyami;
- status() after zapuska soobschaet have_result=True."""
from __future__ import annotations

import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_daily_cycle_run_and_status():
    m = importlib.import_module("modules.memory.daily_cycle")
    assert hasattr(m, "run_cycle"), "daily_cycle.run_cycle missing"
    assert hasattr(m, "status"), "daily_cycle.status missing"

    res = m.run_cycle(mode="test")
    assert isinstance(res, dict)
    assert res.get("slot") in ("A", "B")
    assert "steps" in res
    assert isinstance(res.get("finished_ts"), int)

    st = m.status()
    assert st.get("have_result") is True
    assert st.get("slot") in ("A", "B")