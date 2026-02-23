# -*- coding: utf-8 -*-
from __future__ import annotations

import routes.chat_routes as chat_routes


def _mute_history(monkeypatch) -> None:
    monkeypatch.setattr(chat_routes.hist, "load", lambda sid: [])
    monkeypatch.setattr(chat_routes.hist, "append", lambda sid, role, value: None)


def test_chat_message_live_timeout_fallback(client, auth_hdr_user, monkeypatch):
    _mute_history(monkeypatch)
    monkeypatch.setenv("ESTER_WEB_USE_ARBITRAGE", "1")
    monkeypatch.setattr(
        chat_routes,
        "_call_main_live_arbitrage_with_timeout",
        lambda **kwargs: ("", "timeout"),
    )

    def _fake_llm_chat(*args, **kwargs):
        return {
            "ok": True,
            "provider": "local",
            "answer": "fallback-ok",
            "provider_attempts": [{"provider": "local", "event": "success", "ok": True}],
        }

    monkeypatch.setattr(chat_routes, "llm_chat", _fake_llm_chat)

    r = client.post(
        "/chat/message",
        headers=auth_hdr_user,
        json={"query": "ping", "mode": "local", "temperature": 0.1},
    )
    assert r.status_code == 200, r.data
    payload = r.get_json()
    assert payload["ok"] is True
    assert payload["provider"] == "local"
    assert payload["answer"] == "fallback-ok"
    trace = list(payload.get("provider_trace") or [])
    assert any(str(x.get("provider")) == "hivemind" for x in trace)
    assert any(str(x.get("provider")) == "local" for x in trace)


def test_chat_message_live_success_short_circuit(client, auth_hdr_user, monkeypatch):
    _mute_history(monkeypatch)
    monkeypatch.setenv("ESTER_WEB_USE_ARBITRAGE", "1")
    monkeypatch.setattr(
        chat_routes,
        "_call_main_live_arbitrage_with_timeout",
        lambda **kwargs: ("live-ok", "success"),
    )

    def _must_not_run(*args, **kwargs):
        raise AssertionError("selector fallback should not run when live path succeeded")

    monkeypatch.setattr(chat_routes, "llm_chat", _must_not_run)

    r = client.post(
        "/chat/message",
        headers=auth_hdr_user,
        json={"query": "ping live", "mode": "local"},
    )
    assert r.status_code == 200, r.data
    payload = r.get_json()
    assert payload["ok"] is True
    assert payload["provider"] == "hivemind"
    assert payload["answer"] == "live-ok"
