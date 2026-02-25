# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.mark.parametrize(
    "text",
    [
        "I'm furious and happy at the same time! This is the best and worst day.",
        "I'm sad, but I hope for the best. My heart is pounding with excitement.",
    ],
)
def test_chat_emotions_present(client, auth_hdr_user, text):
    r = client.post(
        "/chat/message",
        headers=auth_hdr_user,
        json={"query": text, "mode": "local", "use_rag": False, "temperature": 0.0},
    )
    assert r.status_code == 200
    j = r.get_json()
    # Struktura
    assert any(k in j for k in ("response", "answer"))
    emo = j.get("emotions") or {}
    # Emotsii nenulevye
    assert isinstance(emo, dict)
    assert len(emo.keys()) > 0
    # The proactive section may be empty, but the field is valid
# assert "proactive" in j