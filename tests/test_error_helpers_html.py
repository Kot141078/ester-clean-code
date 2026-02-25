from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_ocr_runtime_error_renders_help_html():
    from app import app as flask_app
    with flask_app.test_request_context("/", headers={"Accept": "text/html"}):
        from routes.error_helpers import handle_runtime_error  # type: ignore
        resp = handle_runtime_error(RuntimeError("tesseract not found"))
        # for HTML content returns a 200 OK template with hints
        assert isinstance(resp, tuple)
        html, status = resp  # render_template(...), 200
        assert status == 200