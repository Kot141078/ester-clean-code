# -*- coding: utf-8 -*-
"""
routes/auth_roles_routes.py - REST: /auth/roles/me

Most (yavnyy):
- (Veb ↔ RBAC) Vozvraschaet roli, vidimye serverom dlya tekuschey sessii.

Mosty (skrytye):
- (Diagnostika ↔ Integratsiya) Polezno pri nastroyke proksi/IdP i proverke tsepochki avtorizatsii.
- (Politiki ↔ Bezopasnost) UI mozhet podsvechivat dostupnye deystviya na osnove otvetov.

Zemnoy abzats:
Bystryy «kto ya»: endpoint otdaet spisok roley polzovatelya iz RBAC-yadra.
Esli RBAC-modul ne zagruzhen, vozvraschaem yavnuyu oshibku - eto pomogaet ne iskat «seruyu knopku».
"""
from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auth_roles_routes", __name__)

def register(app):
    """Drop-in registratsiya blyuprinta."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


# Pytaemsya importirovat RBAC-yadro; esli ego net - vozvraschaem kontroliruemuyu oshibku
try:
    from modules.auth.rbac import user_roles as _roles  # type: ignore
except Exception:  # pragma: no cover
    _roles = None  # type: ignore


@bp.get("/auth/roles/me")
def api_me():
    """Vozvraschaet roli tekuschego polzovatelya po dannym RBAC-modulya."""
    if _roles is None:
        return jsonify({"ok": False, "error": "rbac_unavailable"}), 500

    try:
        roles = _roles()  # kontrakt ostavlyaem kak v dampe
        return jsonify({"ok": True, "roles": roles})
    except Exception as e:
        # Otdaem tekst oshibki kak est, bez trassy
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp", "register", "init_app"]
# c=a+b