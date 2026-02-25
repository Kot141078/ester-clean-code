# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Separate page for managing backups: /backup/oh
backup_ui_bp = Blueprint("backup_ui", __name__)


@backup_ui_bp.get("/backup/ui")
def backup_ui_index():
    return render_template("backup_ui.html")


@backup_ui_bp.get("/backup/ui/")
def backup_ui_index_slash():
    return render_template("backup_ui.html")


def register_backup_ui(app, url_prefix: str | None = None) -> None:
    """Dump compatible logger. By default it registers /bachkup/oh.
    If url_prefix is ​​passed, add a duplicate for ZZF0Z/bachkup/oh."""
    if url_prefix:
        prefixed = Blueprint("backup_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/backup/ui")
        def _backup_ui_pref():
            return render_template("backup_ui.html")

        @prefixed.get("/backup/ui/")
        def _backup_ui_pref_slash():
            return render_template("backup_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(backup_ui_bp)


def register(app):
    app.register_blueprint(backup_ui_bp)
    return app