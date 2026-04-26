from __future__ import annotations

import json

from modules import sister_autochat


def _set_base_env(monkeypatch) -> None:
    monkeypatch.setenv("SISTER_AUTOCHAT", "1")
    monkeypatch.setenv("SISTER_AUTOCHAT_ROLE", "initiator")
    monkeypatch.setenv("SISTER_NODE_URL", "http://sister.local")
    monkeypatch.setenv("SISTER_SYNC_TOKEN", "shared-secret")
    monkeypatch.setenv("ESTER_NODE_ID", "ester-test")
    monkeypatch.setenv("SISTER_AUTOCHAT_JITTER_SEC", "0")
    monkeypatch.setenv("SISTER_AUTOCHAT_MIN_INTERVAL_SEC", "0")
    monkeypatch.setenv("SISTER_AUTOCHAT_USER_IDLE_SEC", "0")
    monkeypatch.setenv("SISTER_AUTOCHAT_MAX_PER_HOUR", "10")


def test_autochat_enabled_without_armed_flag_does_not_start_thread(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.delenv("SISTER_AUTOCHAT_ARMED", raising=False)

    started = False

    def fake_start(_self):
        nonlocal started
        started = True

    monkeypatch.setattr(sister_autochat.threading.Thread, "start", fake_start)

    assert sister_autochat.start_sister_autochat_background() is None
    assert started is False


def test_autochat_armed_oneshot_sends_once_and_stops(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("SISTER_AUTOCHAT_ARMED", "1")
    monkeypatch.setenv("SISTER_AUTOCHAT_ONESHOT", "1")
    monkeypatch.setattr(sister_autochat, "_network_allowed_for_url", lambda _url: True)
    monkeypatch.setattr(sister_autochat.random, "choice", lambda rows: rows[0])

    sent: list[dict] = []

    def fake_post_json(_url, payload, timeout=5.0):
        sent.append(dict(payload))
        return 200, json.dumps({"status": "success", "content": "ready"})

    monkeypatch.setattr(sister_autochat, "_post_json", fake_post_json)

    ac = sister_autochat.SisterAutoChat()
    ac.run_forever()

    assert len(sent) == 1
    assert sent[0]["type"] == "thought_request"
    assert sent[0]["sender"] == "ester-test"
    assert sent[0]["token"] == "shared-secret"
    assert ac._stop.is_set()
