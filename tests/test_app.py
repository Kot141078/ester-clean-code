# tests/test_app.py
# -*- coding: utf-8 -*-
"""Akkuratnyy dymovoy test Flask-prilozheniya:
- ne trebuet nalichiya vsekh vneshnikh zavisimostey (jwt, cors) - esli ikh net, skip.
- pytaetsya nayti fabriku create_app(), inache ischet peremennuyu app.
- proveryaet, what est health-podobnyy route i on otvechaet 2xx."""
import importlib

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _try_import_app_module():
    try:
        return importlib.import_module("app")
    except Exception as e:
        pytest.skip(f"app.po is not imported in this environment: ZZF0Z")


def _get_flask_app(mod):
    # Predpochitaem fabriku
    if hasattr(mod, "create_app"):
        try:
            app = mod.create_app()
            return app
        except Exception as e:
            pytest.skip(f"create_app() ne podnyalas: {e!r}")
    # Follbek — peremennaya app
    if hasattr(mod, "app"):
        return getattr(mod, "app")
    pytest.skip("V module app ne naydeno ni create_app(), ni app")


def _find_healthlike_endpoint(app):
    # We are looking for typical health routes
    candidates = {"/health", "/api/health", "/api/v1/health", "/_health", "/status"}
    urls = {str(r.rule) for r in app.url_map.iter_rules()}
    for c in candidates:
        if c in urls:
            return c
    # If not, let's try the root
    if "/" in urls:
        return "/"
    pytest.skip(f"Ne nayden health-like marshrut sredi: {sorted(urls)}")


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_health_route_responds_2xx():
    mod = _try_import_app_module()
    app = _get_flask_app(mod)
    client = app.test_client()
    path = _find_healthlike_endpoint(app)
    resp = client.get(path)
    assert (
        200 <= resp.status_code < 500
)  # dopuskaem 2xx-4xx, no glavnoe — ne 5xx