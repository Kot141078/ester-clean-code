# -*- coding: utf-8 -*-
"""Smoke-test dlya routes.memory_experience_routes_alias.

Check it out:
- modul importiruetsya;
- blueprint registriruetsya vo Flask-prilozhenii;
- endpoint /memory/experience/profile otvechaet JSON s polem ok."""

import importlib

from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_memory_experience_routes_alias_import_and_api():
    m = importlib.import_module("routes.memory_experience_routes_alias")
    assert hasattr(m, "bp")

    app = Flask(__name__)
    app.register_blueprint(m.bp)

    client = app.test_client()
    rv = client.get("/memory/experience/profile")

    assert rv.status_code in (200, 500)
    data = rv.get_json()
    assert isinstance(data, dict)
    assert "ok" in data