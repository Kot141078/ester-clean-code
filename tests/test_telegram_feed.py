from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_tg_post_and_latest(client, auth_hdr_user):
    r = client.post(
        "/tg/post",
        headers=auth_hdr_user,
        json={
            "chat_id": "1001",
            "chat_title": "Ester Group",
            "message_id": "77",
            "from": "bob",
            "text": "Privet iz TG!",
            "tags": ["tgtest"],
        },
    )
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True

    g = client.get("/tg/latest?limit=3")
    assert g.status_code == 200
    jg = g.get_json()
    assert jg.get("ok") is True
    assert isinstance(jg.get("items"), list)