from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_providers_status_and_select(client, auth_hdr_admin):
    r = client.get("/providers/status", headers=auth_hdr_admin)
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert "providers" in j and "active" in j

    # select (esli rout podklyuchen)
    sel = client.post("/providers/select", headers=auth_hdr_admin, json={"name": j.get("active")})
    assert sel.status_code in (200, 400)


def test_chat_message_ok(client, auth_hdr_user):
    r = client.post(
        "/chat/message",
        headers=auth_hdr_user,
        json={
            "query": "Plan replikatsii i bekapov?",
            "mode": "judge",
            "use_rag": True,
            "temperature": 0.0,
        },
    )
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert "answer" in j
    assert "memory_hits" in j
    assert "filters" in j


def test_chat_message_400(client, auth_hdr_user):
    r = client.post("/chat/message", headers=auth_hdr_user, json={"query": ""})
# assert r.status_code in (400, 404)