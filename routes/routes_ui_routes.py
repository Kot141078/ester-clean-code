# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Separate page review of pens: /rutes/oh
# Drop-in: does not break existing /Rute (ZhSON or other implementation); This is only an HTML showcase.

routes_ui_bp = Blueprint("routes_ui", __name__)


@routes_ui_bp.get("/routes/ui")
def routes_ui_index():
    return render_template("routes_index.html")


@routes_ui_bp.get("/routes/ui/")
def routes_ui_index_slash():
    return render_template("routes_index.html")


def register_routes_ui(app, url_prefix: str | None = None) -> None:
    """Dump compatible logger. By default it registers /rutes/oi.
    If url_prefix is ​​passed, add a duplicate for ZZF0Z/RUTE/oi."""
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