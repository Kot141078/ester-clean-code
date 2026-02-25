# -*- coding: utf-8 -*-
"""routes/ops_help_routes.py - stranitsa s offlayn-podskazkami po ustanovke OCR-zavisimostey.

Route:
  GET /ops/ingest/help -> HTML (templates/ops_ingest_help.html)

Mosty:
- Yavnyy: (OPS ↔ UI) bystryy dostup k instruktsiyam pryamo iz paneli.
- Skrytyy #1: (Inzheneriya ↔ Prozrachnost) khranenie spravki v shablonakh, bez vneshnikh zavisimostey.
- Skrytyy #2: (Sovmestimost ↔ Kontrakty) drop-in blueprint s register/init_app i aliasom.

Zemnoy abzats:
Eto “pamyatka na stene” v servernoy: vsegda pod rukoy, dazhe bez interneta.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, render_template
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap
try:
    from modules.auth.rbac import has_any_role as _has_any_role
except Exception:
    def _has_any_role(_required):  # type: ignore
        return True
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ops_help_bp = Blueprint("ops_help", __name__, url_prefix="/ops")


@ops_help_bp.get("/ingest/help")
@jwt_required()
def ops_ingest_help():
    if not _has_any_role(["admin", "operator"]):
        return ("forbidden", 403)
    return render_template("ops_ingest_help.html")


def register_ops_help_routes(app, url_prefix: str | None = None) -> None:  # pragma: no cover
    """Compatible blueprint registration with optional prefix override."""
    if url_prefix is None:
        app.register_blueprint(ops_help_bp)
    else:
        app.register_blueprint(ops_help_bp, url_prefix=url_prefix)


# Unified project hooks
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(ops_help_bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(ops_help_bp)


__all__ = ["ops_help_bp", "register_ops_help_routes", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(ops_help_bp)
    return app
