# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Separate page for uploading files: /upload/oh (and alias /ingest/oh)
upload_ui_bp = Blueprint("upload_ui", __name__)


@upload_ui_bp.get("/upload/ui")
def upload_ui_index():
    return render_template("upload_ui.html")


@upload_ui_bp.get("/upload/ui/")
def upload_ui_index_slash():
    return render_template("upload_ui.html")


# Aliasy pod ingest
@upload_ui_bp.get("/ingest/ui")
def ingest_ui_index():
    return render_template("upload_ui.html")


@upload_ui_bp.get("/ingest/ui/")
def ingest_ui_index_slash():
    return render_template("upload_ui.html")


def register_upload_ui(app, url_prefix: str | None = None) -> None:
    """Sovmestimyy s dampom registrar. Po umolchaniyu register /upload/ui i /ingest/ui.
    Esli peredan url_prefix - add dubl po {url_prefix}/upload/ui Re {url_prefix}/ingest/ui."""
    if url_prefix:
        prefixed = Blueprint("upload_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/upload/ui")
        def _upload_ui_pref():
            return render_template("upload_ui.html")

        @prefixed.get("/upload/ui/")
        def _upload_ui_pref_slash():
            return render_template("upload_ui.html")

        @prefixed.get("/ingest/ui")
        def _ingest_ui_pref():
            return render_template("upload_ui.html")

        @prefixed.get("/ingest/ui/")
        def _ingest_ui_pref_slash():
            return render_template("upload_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(upload_ui_bp)


def register(app):
    app.register_blueprint(upload_ui_bp)
    return app