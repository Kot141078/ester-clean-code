from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_chat_message_happy_path(client, auth_hdr_user):
    r = client.post(
        "/chat/message",
        json={
            "mode": "local",
            "query": "Hello! How are you?",
            "use_rag": False,
            "temperature": 0.0,
        },
        headers=auth_hdr_user,
    )
    assert r.status_code == 200, r.data
    j = r.get_json()
    assert "response" in j
    assert "emotions" in j
    assert "proactive" in j
    assert "rag" in j


def test_chat_message_empty_query(client, auth_hdr_user):
    r = client.post("/chat/message", json={"query": ""}, headers=auth_hdr_user)
    assert r.status_code == 400
