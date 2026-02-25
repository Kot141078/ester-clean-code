# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Separate provider management page: /providers/oh
providers_ui_bp = Blueprint("providers_ui", __name__)


@providers_ui_bp.get("/providers/ui")
def providers_ui_index():
    return render_template("providers_ui.html")


@providers_ui_bp.get("/providers/ui/")
def providers_ui_index_slash():
    return render_template("providers_ui.html")


def register_providers_ui(app, url_prefix: str | None = None) -> None:
    """Dump compatible logger. By default registers /provider/oi.
    If url_prefix is ​​passed, add a duplicate for ZZF0Z/provider/oi."""
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