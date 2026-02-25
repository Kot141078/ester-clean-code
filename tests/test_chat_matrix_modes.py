# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.mark.parametrize("mode", ["local", "cloud", "judge"])
@pytest.mark.parametrize("use_rag", [False, True])
@pytest.mark.parametrize("temp", [0.0, 0.9])
def test_chat_matrix_ok(client, auth_hdr_user, mode, use_rag, temp):
    r = client.post(
        "/chat/message",
        headers=auth_hdr_user,
        json={
            "query": f"Matritsa chata: mode={mode}, rag={use_rag}, t={temp}",
            "mode": mode,
            "use_rag": use_rag,
            "temperature": temp,
        },
    )
    assert r.status_code == 200
    j = r.get_json()
    # allows different answer keys
    assert any(k in j for k in ("response", "answer"))
    assert "emotions" in j
    assert "proactive" in j
    # if rag is enabled, expect the presence of a rag field (may be empty)
    if use_rag:
        assert "rag" in j


def test_chat_400_empty_query(client, auth_hdr_user):
    r = client.post("/chat/message", headers=auth_hdr_user, json={"query": ""})
    assert r.status_code in (400, 422)


def test_chat_401_no_jwt(client):
    r = client.post("/chat/message", json={"query": "privet"})
    assert r.status_code in (401, 403, 422)


def test_chat_403_rbac_denied_when_configured(client, auth_hdr_user, monkeypatch):
    # If strict RVACH is enabled in the environment, /chat can be allowed - then we will skip the test
    r = client.get("/routes", headers=auth_hdr_user)
    if r.status_code == 200:
        pytest.skip(
            "RVACH allows /chat for the user role - negative case is not applicable"
)