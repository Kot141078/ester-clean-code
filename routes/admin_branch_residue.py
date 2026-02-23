# -*- coding: utf-8 -*-
"""
routes/admin_branch_residue.py

UI page:
  GET /admin/branch_residue
"""
from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("admin_branch_residue", __name__, url_prefix="/admin")


@bp.get("/branch_residue")
def page():
    return render_template("admin_branch_residue.html")


def register(app):
    app.register_blueprint(bp)
    return app

