# -*- coding: utf-8 -*-
"""
routes/admin_retrieval_router_metrics.py

UI page:
  GET /admin/retrieval_router
"""
from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("admin_retrieval_router_metrics", __name__, url_prefix="/admin")


@bp.get("/retrieval_router")
def page():
    return render_template("admin_retrieval_router_metrics.html")


def register(app):
    app.register_blueprint(bp)
    return app

