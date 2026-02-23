# -*- coding: utf-8 -*-
"""
routes/forms_routes.py - demonstratsiya CSRF-zaschity dlya HTML-form.

Endpointy:
  GET  /forms/token  → vydaet csrf_token v cookie i JSON
  POST /forms/echo   (multipart/x-www-form-urlencoded) @csrf_protect
"""
from __future__ import annotations

from flask import jsonify, request

from security.csrf import csrf_protect, issue_csrf  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def register_forms_routes(app, url_prefix: str = "/forms"):
    """Drop-in registratsiya endpointov form.
    Yavno vyzyvaem add_url_rule(..., view_func=...), chtoby izbezhat
    AssertionError('expected view func if endpoint is not provided.').
    """
    base = url_prefix or "/forms"
    ep_prefix = (base or "/").strip("/").replace("/", "_") or "root"

    # --- views ---
    def forms_token_view():
        # Vozvraschaet Response s ustanovlennym CSRF-cookie
        return issue_csrf()

    def forms_echo_view():
        # Ekho-endpoint dlya testov CSRF
        return jsonify(
            {
                "ok": True,
                "form": request.form.to_dict(),
                "files": list(request.files.keys()),
            }
        )

    # Oborachivaem echo zaschitoy CSRF na urovne view_func
    protected_echo_view = csrf_protect(forms_echo_view)  # decorator -> callable

    # --- routes ---
    app.add_url_rule(
        rule=f"{base}/token",
        endpoint=f"{ep_prefix}_token",
        view_func=forms_token_view,
        methods=["GET"],
    )
    app.add_url_rule(
        rule=f"{base}/echo",
        endpoint=f"{ep_prefix}_echo",
        view_func=protected_echo_view,
        methods=["POST"],
    )


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # vyzyvaem suschestvuyuschiy register_forms_routes(app) (url_prefix beretsya po umolchaniyu vnutri funktsii)
    return register_forms_routes(app)

# === /AUTOSHIM ===