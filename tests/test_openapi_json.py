from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_openapi_json_has_chat_message(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, dict)
    # Proverim nalichie puti /chat/message (ili sovmestimyy /chat)
    paths = j.get("paths") or {}
    assert "/chat/message" in paths or "/chat" in paths