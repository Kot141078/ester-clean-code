# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Otdelnaya vitrina dokumentatsii: /docs/ui
docs_ui_bp = Blueprint("docs_ui", __name__)


@docs_ui_bp.get("/docs/ui")
def docs_ui_index():
    return render_template("docs_ui.html")


@docs_ui_bp.get("/docs/ui/")
def docs_ui_index_slash():
    return render_template("docs_ui.html")


def register_docs_ui(app, url_prefix: str | None = None) -> None:
    """
    Sovmestimyy s dampom registrator. Po umolchaniyu registriruet /docs/ui.
    Esli peredan url_prefix — dobavit dubl po {url_prefix}/docs/ui.
    """
    if url_prefix:
        prefixed = Blueprint("docs_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/docs/ui")
        def _docs_ui_pref():
            return render_template("docs_ui.html")

        @prefixed.get("/docs/ui/")
        def _docs_ui_pref_slash():
            return render_template("docs_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(docs_ui_bp)


def register(app):
    app.register_blueprint(docs_ui_bp)
    return app