# -*- coding: utf-8 -*-
"""
tests/test_admin_reports_json.py — smoke-test agregatora otchetov /admin/reports/json.
Test nezavisimo registriruet blyuprint v prilozhenii testovogo klienta.
"""

from __future__ import annotations

import json
import os

from routes.admin_reports_routes import register_admin_reports_routes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_admin_reports_json(client, admin_jwt, monkeypatch, tmp_path):
    # Izoliruem PERSIST_DIR i sozdadim fiktivnye otchety
    base = tmp_path / "data"
    monkeypatch.setenv("PERSIST_DIR", str(base))
    (base / "dreams").mkdir(parents=True, exist_ok=True)
    (base / "gc").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)

    (base / "dreams" / "last_report.json").write_text(
        json.dumps({"ok": True, "clusters": 2, "hypotheses": 3, "saved": 3}, ensure_ascii=False),
        encoding="utf-8",
    )
    (base / "gc" / "last_report.json").write_text(
        json.dumps({"ok": True, "decayed_edges": 5, "removed_edges": 2}, ensure_ascii=False),
        encoding="utf-8",
    )
    (base / "reports" / "last_report.json").write_text(
        json.dumps({"ok": True, "steps": [{"kg": {"ok": True}}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    # Zaregistriruem blyuprint na tekuschem prilozhenii test-klienta
    app = client.application
    register_admin_reports_routes(app)

    # Vyzov JSON-agregatora
    r = client.get("/admin/reports/json", headers={"Authorization": f"Bearer {admin_jwt}"})
    assert r.status_code == 200, r.data
    js = r.get_json()
    assert js["ok"] is True
    assert js["dreams"]["ok"] is True
    assert js["gc"]["ok"] is True
    assert js["rebuild"]["ok"] is True
