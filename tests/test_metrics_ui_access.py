# -*- coding: utf-8 -*-
import json
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_metrics_ui_access_admin(monkeypatch):
    # We allow a simple login and the RVACH matrix
    monkeypatch.setenv("ENABLE_SIMPLE_LOGIN", "1")
    monkeypatch.setenv("RBAC_MODE", "matrix")
    monkeypatch.setenv("RBAC_MATRIX_PATH", "rules/rbac_matrix.yaml")

    from app import app as flask_app
    c = flask_app.test_client()

    # Login pod adminom
    r = c.post("/auth/login", data=json.dumps({"user": "ci", "role": "admin"}), content_type="application/json")
    assert r.status_code == 200
    token = r.get_json()["access_token"]

    # Stranitsa metrik UI
    r2 = c.get("/metrics/ui", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    html = r2.get_data(as_text=True)
    assert "Metriki" in html or "metrics" in html.lower()