# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Otdelnaya stranitsa-obzor ruchek: /routes/ui
# Drop-in: ne lomaet suschestvuyuschie /routes (JSON ili drugaya realizatsiya); eto tolko HTML-vitrina.

routes_ui_bp = Blueprint("routes_ui", __name__)


@routes_ui_bp.get("/routes/ui")
def routes_ui_index():
    return render_template("routes_index.html")


@routes_ui_bp.get("/routes/ui/")
def routes_ui_index_slash():
    return render_template("routes_index.html")


def register_routes_ui(app, url_prefix: str | None = None) -> None:
    """
    Sovmestimyy s dampom registrator. Po umolchaniyu registriruet /routes/ui.
    Esli peredan url_prefix — dobavit dubl po {url_prefix}/routes/ui.
    """
    if url_prefix:
        prefixed = Blueprint("routes_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/routes/ui")
        def _routes_ui_pref():
            return render_template("routes_index.html")

        @prefixed.get("/routes/ui/")
        def _routes_ui_pref_slash():
            return render_template("routes_index.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(routes_ui_bp)


def register(app):
    app.register_blueprint(routes_ui_bp)
    return app