# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Otdelnaya stranitsa statusa: /status/ui
health_ui_bp = Blueprint("health_ui", __name__)


@health_ui_bp.get("/status/ui")
def health_ui_index():
    return render_template("health_ui.html")


@health_ui_bp.get("/status/ui/")
def health_ui_index_slash():
    return render_template("health_ui.html")


def register_health_ui(app, url_prefix: str | None = None) -> None:
    """
    Sovmestimyy s dampom registrator. Po umolchaniyu registriruet /status/ui.
    Esli peredan url_prefix — dobavit dubl po {url_prefix}/status/ui.
    """
    if url_prefix:
        prefixed = Blueprint("health_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/status/ui")
        def _health_ui_pref():
            return render_template("health_ui.html")

        @prefixed.get("/status/ui/")
        def _health_ui_pref_slash():
            return render_template("health_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(health_ui_bp)


def register(app):
    app.register_blueprint(health_ui_bp)
    return app