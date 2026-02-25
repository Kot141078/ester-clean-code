# -*- coding: utf-8 -*-
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _post(client, url, json, headers):
    return client.post(url, json=json, headers=headers)


def test_chat_message_local(client, auth_header):
    r = _post(
        client,
        "/chat/message",
        {
            "query": "Privet, kto ty?",
            "mode": "local",
            "user": "Owner",
            "persona": "drug i kompanon",
        },
        auth_header,
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["mode"] == "local"
    assert "response" in data and isinstance(data["response"], str)
    assert data["providers_local"]  # spisok est
    # RAG sources must be present (mocks return 2 chunks)
    assert isinstance(data.get("sources"), list) and len(data["sources"]) >= 1


def test_chat_message_cloud_judge_merge(client, auth_header):
    # cloud mode - association through a judge by default
    r = _post(
        client,
        "/chat/message",
        {
            "query": "Sdelay kratkoe sammari 'Voyna i mir'",
            "mode": "cloud",
            "user": "Owner",
        },
        auth_header,
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["mode"] == "cloud"
    assert data.get("judge") in ("openai", "lmstudio", "gemini")


def test_chat_message_explicit_judge(client, auth_header):
    r = _post(
        client,
        "/chat/message",
        {
            "query": "Compare Pothon and Go for microservices",
            "mode": "judge",
            "judge": "openai",
            "user": "Owner",
        },
        auth_header,
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["mode"] == "judge"
# assert data["judge"] == "openai"