# -*- coding: utf-8 -*-
from flask import url_for
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_error_helper_ocr_hint(monkeypatch):
    from app import app as flask_app
    # Symitiruem vyzov obrabotchika vnutri request-sessii
    with flask_app.test_request_context("/", headers={"Accept": "application/json"}):
        from routes.error_helpers import handle_runtime_error  # type: ignore
        resp, status = handle_runtime_error(RuntimeError("tesseract not found"))
        assert status == 400
        assert resp.json["error"] == "ocr_dependency_missing"
        assert resp.json["help_url"] == "/ops/ingest/help"

def test_error_helper_generic(monkeypatch):
    from app import app as flask_app
    with flask_app.test_request_context("/", headers={"Accept": "application/json"}):
        from routes.error_helpers import handle_runtime_error  # type: ignore
        resp, status = handle_runtime_error(RuntimeError("random failure"))
        assert status == 400
        assert resp.json["error"] == "runtime_error"