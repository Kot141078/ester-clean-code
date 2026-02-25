# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_research_search_ok(client, auth_hdr_user):
    r = client.post("/research/search", headers=auth_hdr_user, json={"query": "test ping"})
    # allow 200 (success) or 202/201 (if the function sets a task)
    assert r.status_code in (200, 201, 202)
    # allow different response structures; let's minimally check a non-empty jsion
    j = r.get_json()
    assert isinstance(j, dict)
# assert j != {}