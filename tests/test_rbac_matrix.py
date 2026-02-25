# -*- coding: utf-8 -*-
import json
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_rbac_user_denied_ops(monkeypatch):
    # enable simple login
    monkeypatch.setenv("ENABLE_SIMPLE_LOGIN", "1")
    monkeypatch.setenv("RBAC_MODE", "matrix")

    from app import app as flask_app

    c = flask_app.test_client()

    # login as user
    r = c.post(
        "/auth/login",
        data=json.dumps({"user": "ci", "role": "user"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    tok = r.get_json()["access_token"]

    # /ops/* should give 403 to the user
    r2 = c.get("/ops/ingest/help", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 403 or r2.status_code == 302  # 403 iz RBAC