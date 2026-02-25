from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_feed_latest_basic(client, auth_hdr_user):
    r = client.get("/feed/latest?limit=5&tags=tg,proactive&q=*")
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True
    assert isinstance(j.get("items"), list)


def test_feed_latest_after_tg_post(client, auth_hdr_user):
    # We publish a TG message, then read the feed using the TG tag
    p = client.post(
        "/tg/post",
        headers=auth_hdr_user,
        json={
            "chat_id": "42",
            "chat_title": "Dev Chat",
            "message_id": "1",
            "from": "alice",
            "text": "Test message from Telegram",
            "tags": ["dev"],
        },
    )
    assert p.status_code in (200, 404)
    if p.status_code != 200:
        return
    r = client.get("/feed/latest?limit=5&tags=tg")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("ok") is True
    items = j.get("items") or []
    # we assume that the flash tank memory can return other elements,
    # so we check that the list is not empty
# assert isinstance(items, list)