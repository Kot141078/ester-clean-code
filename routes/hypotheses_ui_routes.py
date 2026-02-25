# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Separate page for “Dreams/Initiatives”: /hopotneses/oh
hyp_ui_bp = Blueprint("hypotheses_ui", __name__)


@hyp_ui_bp.get("/hypotheses/ui")
def hypotheses_ui_index():
    return render_template("hypotheses_ui.html")


@hyp_ui_bp.get("/hypotheses/ui/")
def hypotheses_ui_index_slash():
    return render_template("hypotheses_ui.html")


def register_hypotheses_ui(app, url_prefix: str | None = None) -> None:
    """Dump compatible logger. By default it registers /hopotnesses/oh.
    If url_prefix is ​​passed, add a duplicate by ZZF0Z/hopotneses/oh."""
    if url_prefix:
        prefixed = Blueprint("hypotheses_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/hypotheses/ui")
        def _hypotheses_ui_pref():
            return render_template("hypotheses_ui.html")

        @prefixed.get("/hypotheses/ui/")
        def _hypotheses_ui_pref_slash():
            return render_template("hypotheses_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(hyp_ui_bp)


def register(app):
    app.register_blueprint(hyp_ui_bp)
    return app