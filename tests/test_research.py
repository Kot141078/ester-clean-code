from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_research_search_get(client, auth_hdr_user):
    r = client.get("/research/search", query_string={"query": "hello ester"}, headers=auth_hdr_user)
    assert r.status_code == 200
    j = r.get_json()
    assert "results" in j and isinstance(j["results"], list)


def test_research_search_post(client, auth_hdr_user):
    r = client.post("/research/search", json={"query": "status"}, headers=auth_hdr_user)
    assert r.status_code == 200
    j = r.get_json()
# assert "results" in j and isinstance(j["results"], list)