# -*- coding: utf-8 -*-
import os
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_ops_help_page_admin(monkeypatch):
    monkeypatch.setenv("ENABLE_SIMPLE_LOGIN", "1")
    monkeypatch.setenv("RBAC_MODE", "matrix")

    from app import app as flask_app
    c = flask_app.test_client()

    r = c.post("/auth/login", data=json.dumps({"user":"ci","role":"admin"}), content_type="application/json")
    tok = r.get_json()["access_token"]

    r2 = c.get("/ops/ingest/help", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200
    assert "OCR/INGEST" in r2.get_data(as_text=True)