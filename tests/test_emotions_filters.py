# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.mark.parametrize(
    "text",
    [
        "Ya v yarosti i schastliv odnovremenno! Eto luchshiy i khudshiy den.",
        "Mne grustno, no ya nadeyus na luchshee. Serdtse kolotitsya ot volneniya.",
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
    # Proaktivnaya sektsiya mozhet byt pustoy, no pole dopustimo
# assert "proactive" in j