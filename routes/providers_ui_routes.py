# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Otdelnaya stranitsa upravleniya provayderami: /providers/ui
providers_ui_bp = Blueprint("providers_ui", __name__)


@providers_ui_bp.get("/providers/ui")
def providers_ui_index():
    return render_template("providers_ui.html")


@providers_ui_bp.get("/providers/ui/")
def providers_ui_index_slash():
    return render_template("providers_ui.html")


def register_providers_ui(app, url_prefix: str | None = None) -> None:
    """
    Sovmestimyy s dampom registrator. Po umolchaniyu registriruet /providers/ui.
    Esli peredan url_prefix — dobavit dubl po {url_prefix}/providers/ui.
    """
    if url_prefix:
        prefixed = Blueprint("providers_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/providers/ui")
        def _providers_ui_pref():
            return render_template("providers_ui.html")

        @prefixed.get("/providers/ui/")
        def _providers_ui_pref_slash():
            return render_template("providers_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(providers_ui_bp)


def register(app):
    app.register_blueprint(providers_ui_bp)
    return app