# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, redirect
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Vlyuprint svodnogo interfeysa: /portal
# Drop-in sovmestimost: ne menyaet suschestvuyuschie importy/puti, tolko dobavlyaet HTML-vitrinu.

portal_bp = Blueprint("portal", __name__)


@portal_bp.get("/portal")
def portal_index():
    return redirect("/admin/portal", code=302)


@portal_bp.get("/portal/")
def portal_index_slash():
    return redirect("/admin/portal", code=302)


def register_portal_routes(app, url_prefix: str | None = None) -> None:
    """
    Sovmestimyy registrator. Po umolchaniyu registriruet /portal.
    Esli peredan url_prefix — dobavit dubl po {url_prefix}/portal.
    """
    if url_prefix:
        prefixed = Blueprint("portal_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/portal")
        def _portal_pref():
            return redirect("/admin/portal", code=302)

        @prefixed.get("/portal/")
        def _portal_pref_slash():
            return redirect("/admin/portal", code=302)

        app.register_blueprint(prefixed)

# app.register_blueprint(portal_bp)


def register(app):
    app.register_blueprint(portal_bp)
    return app
