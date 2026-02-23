# -*- coding: utf-8 -*-
from app import app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_probe_golden_smoke():
    c = app.test_client()
    rv = c.get("/ops/probe/golden")
    assert rv.status_code in (200, 503)
    data = rv.get_json()
    assert isinstance(data, dict)
    assert "value" in data


def test_probe_llm_smoke():
    c = app.test_client()
    rv = c.get("/ops/probe/llm")
    assert rv.status_code in (200, 503)
    data = rv.get_json()
    assert isinstance(data, dict)
    assert "value" in data
# assert "details" in data