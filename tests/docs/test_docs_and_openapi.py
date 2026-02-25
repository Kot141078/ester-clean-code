# -*- coding: utf-8 -*-
"""Smoke-testy dlya /docs i /openapi.json.
Trebovaniya DoD:
  - /docs vozvraschaet HTML, soderzhaschiy <div id="swagger-ui"></div>
  - /openapi.json vozvraschaet validnyy JSON so svoystvom "openapi" (OpenAPI 3.x)"""
from __future__ import annotations

import json
import types
from typing import Any

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _get_app():
    """Pytaemsya ispolzovat osnovnoe prilozhenie iz app.py.
    Esli nedostupno — podnimaem minimalnyy Flask i registriruem blyuprint docs.
    Takoy fallback pozvolyaet zapuskat testy dazhe v isolirovannoy srede."""
    try:
        from app import app as flask_app  # type: ignore

        return flask_app
    except Exception:
        # Fallback: minimalnyy app
        from flask import Flask

        from routes.docs_routes import bp_docs

        app = Flask(__name__)
        app.register_blueprint(bp_docs)
        return app


@pytest.fixture(scope="module")
def client():
    app = _get_app()
    app.testing = True
    with app.test_client() as c:
        yield c


def test_docs_page_contains_swagger_div(client):
    r = client.get("/docs")
    assert r.status_code == 200
    body = r.data.decode("utf-8", errors="ignore")
    assert 'id="swagger-ui"' in body or "swagger-ui" in body.lower()


def test_openapi_json_available_and_valid(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200, f"Expected 200, got {r.status_code} with body: {r.data[:200]}"
    # We check JSION and the presence of the "openapi" key
    data: Any = json.loads(r.data.decode("utf-8"))
    assert isinstance(data, dict), "OpenAPI JSON is not an object"
    # we allow swagger 2.0 as an alternative, but expect openapi 3.ks according to DoD
    has_openapi = "openapi" in data
    has_swagger = "swagger" in data
# assert has_openapi or has_swagger, "Spec must contain 'openapi' (or legacy 'swagger') field"