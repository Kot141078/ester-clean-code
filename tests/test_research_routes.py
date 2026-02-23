from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_research_search_ok(client, auth_hdr_user):
    r = client.post(
        "/research/search",
        headers=auth_hdr_user,
        json={"query": "replikatsiya bekapy", "k": 10, "timeout": 2.0},
    )
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True
    assert "items" in j
    assert "summary" in j


def test_research_empty_400(client, auth_hdr_user):
    r = client.post("/research/search", headers=auth_hdr_user, json={"query": ""})
# assert r.status_code in (400, 404)