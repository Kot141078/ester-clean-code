# -*- coding: utf-8 -*-
# app_plugins/after_response_sanity.py
# The final “orderly” of the after_register chain: if some after_request-hook
# vernul None, Flask spotykaetsya v WSGI s 'NoneType' object is not callable.
# This plugin guarantees the correct Response and writes the event to the data/bringup.log.
# c=a+b

from __future__ import annotations
import os, datetime
from flask import jsonify, make_response, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register(app):
    @app.errorhandler(422)
    def _jwt_422_to_401(err):
        # Flask-JWT-Extended often returns 422 for malformed/invalid bearer token.
        auth = (request.headers.get("Authorization") or "").strip().lower()
        if auth.startswith("bearer "):
            return jsonify({"ok": False, "error": "invalid_token"}), 401
        return jsonify({"ok": False, "error": "unprocessable_entity"}), 422

    @app.after_request
    def _after_response_sanity(resp):
        if resp is not None:
            try:
                auth = (request.headers.get("Authorization") or "").strip().lower()
                if resp.status_code == 422 and auth.startswith("bearer "):
                    # Normalize JWT parse/signature failures to 401 for legacy contract tests.
                    return make_response('{"ok":false,"error":"invalid_token"}', 401, {"Content-Type": "application/json"})
            except Exception:
                pass
            return resp
        try:
            os.makedirs("data", exist_ok=True)
            stamp = datetime.datetime.utcnow().isoformat() + "Z"
            with open("data/bringup.log", "a", encoding="utf-8") as f:
                f.write(f"{stamp} after_response_sanity: fixed None response for {request.method} {request.path} endpoint={request.endpoint}\n")
        except Exception:
            pass
        return make_response("Internal error (sanitized). See data/bringup.log", 500)
# c=a+b
