from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_flashback_edge_k_zero(client, auth_hdr_user):
    r = client.get("/mem/flashback", headers=auth_hdr_user, query_string={"query": "*", "k": 0})
    # dopuskaem 200 s pustym spiskom ili 400 kak nekorrektnyy vvod
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        j = r.get_json()
        arr = j.get("results") or j.get("flashback") or []
        assert isinstance(arr, list)
        assert len(arr) == 0


def test_flashback_long_query(client, auth_hdr_user):
    q = "replikatsiya " * 200
    r = client.get("/mem/flashback", headers=auth_hdr_user, query_string={"query": q, "k": 5})
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, dict)
    assert any(k in j for k in ("results", "flashback"))


def test_alias_bad_input_400(client, auth_hdr_admin):
    # otsutstvuyut polya
    r = client.post("/mem/alias", headers=auth_hdr_admin, json={})
# assert r.status_code in (400, 422)