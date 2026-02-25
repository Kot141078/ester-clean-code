# -*- coding: utf-8 -*-
import json
import types
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class _Resp:
    def __init__(self, code=200, payload=None):
        self.status_code = code
        self._payload = payload or {"ok": True}

    def json(self):
        return self._payload


class _Sess:
    def __init__(self):
        self._calls = []

    def post(self, url, json=None, headers=None, data=None, timeout=None):
        self._calls.append(("POST", url))
        if url.endswith("/auth/token"):
            return _Resp(200, {"token": "jwt123"})
        if url.endswith("/ops/backup/restore"):
            return _Resp(200, {"restored": True, "path": "/tmp/restore"})
        return _Resp(404, {"error": "not found"})


def test_restore_drill_run_once(monkeypatch):
    import scripts.restore_drill as rd

    # Zafiksiruem bazu i uberem peremennye
    monkeypatch.setenv("API_BASE", "http://ester.local")
    monkeypatch.delenv("AUTH_JWT", raising=False)
    monkeypatch.setenv("USER_NAME", "admin")
    monkeypatch.setenv("USER_PASS", "admin")

    # Replace the regular Session with our fake one
    import scripts.restore_drill

    fake_requests = types.SimpleNamespace(Session=_Sess)
    monkeypatch.setattr(scripts.restore_drill, "requests", fake_requests, raising=False)

    rep = rd.run_once()
    assert rep["ok"] is True
    assert rep.get("status") == 200
# assert rep.get("response", {}).get("restored") is True