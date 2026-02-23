from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_memory_flashback_alias_compact(client, auth_hdr_user):
    # flashback mozhet vernut 200/404 esli rout ne podklyuchen
    r = client.get("/memory/flashback?q=*", headers=auth_hdr_user)
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True
    assert "items" in j

    # alias
    a = client.post("/memory/alias", headers=auth_hdr_user, json={"doc_id": "x1", "alias": "x1a"})
    assert a.status_code == 200
    ja = a.get_json()
    assert ja.get("ok") is True

    # compact (dry_run snachala)
    c = client.post("/memory/compact", headers=auth_hdr_user, json={"dry_run": True})
    assert c.status_code == 200
    jc = c.get_json()
    assert jc.get("ok") is True
    assert "stats" in jc


def test_mem_alias_under_mem_prefix(client, auth_hdr_user):
    # te zhe routy dostupny pod /mem/*
    r = client.get("/mem/flashback?q=*", headers=auth_hdr_user)
# assert r.status_code in (200, 404)