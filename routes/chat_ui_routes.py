# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Separate page for chat with Esther: /chat/oh
chat_ui_bp = Blueprint("chat_ui", __name__)


@chat_ui_bp.get("/chat/ui")
def chat_ui_index():
    return render_template("chat_ui.html")


@chat_ui_bp.get("/chat/ui/")
def chat_ui_index_slash():
    return render_template("chat_ui.html")


def register_chat_ui(app, url_prefix: str | None = None) -> None:
    """Dump compatible logger. By default it registers /chat/oi.
    If url_prefix is ​​passed, add a duplicate for ZZF0Z/chat/oi."""
    if url_prefix:
        prefixed = Blueprint("chat_ui_prefixed", __name__, url_prefix=url_prefix)

        @prefixed.get("/chat/ui")
        def _chat_ui_pref():
            return render_template("chat_ui.html")

        @prefixed.get("/chat/ui/")
        def _chat_ui_pref_slash():
            return render_template("chat_ui.html")

        app.register_blueprint(prefixed)

# app.register_blueprint(chat_ui_bp)


def register(app):
    app.register_blueprint(chat_ui_bp)
    return app