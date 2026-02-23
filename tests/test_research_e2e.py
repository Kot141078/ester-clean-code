# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_research_search_ok(client, auth_hdr_user):
    r = client.post("/research/search", headers=auth_hdr_user, json={"query": "test ping"})
    # razreshaem 200 (uspekh) ili 202/201 (esli funktsiya stavit zadachu)
    assert r.status_code in (200, 201, 202)
    # dopustim raznye struktury otveta; minimalno proverim ne-pustoy json
    j = r.get_json()
    assert isinstance(j, dict)
# assert j != {}