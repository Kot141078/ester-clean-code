# -*- coding: utf-8 -*-
"""routes/auth_roles_routes.py - REST: /auth/roles/me

Most (yavnyy):
- (Veb ↔ RBAC) Vozvraschaet roli, vidimye serverom dlya tekuschey sessii.

Mosty (skrytye):
- (Diagnostika ↔ Integratsiya) Polezno pri nastroyke proksi/IdP i proverke tsepochki avtorizatsii.
- (Politiki ↔ Bezopasnost) UI mozhet podsvechivat dostupnye deystviya na osnove otvetov.

Zemnoy abzats:
Bystryy “who ya”: endpoint otdaet spisok roley polzovatelya iz RBAC-yadra.
Esli RBAC-modul ne zagruzhen, vozvraschaem yavnuyu oshibku - eto pomogaet ne iskat “seruyu knopku”."""
from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auth_roles_routes", __name__)

def register(app):
    """Drop-in registration of blueprint."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


# We are trying to import the RVACH core; if it is not there, we return a controlled error
try:
    from modules.auth.rbac import user_roles as _roles  # type: ignore
except Exception:  # pragma: no cover
    _roles = None  # type: ignore


@bp.get("/auth/roles/me")
def api_me():
    """Returns the roles of the current user according to the RVACH module data."""
    if _roles is None:
        return jsonify({"ok": False, "error": "rbac_unavailable"}), 500

    try:
        roles = _roles()  # leave the contract as in the dump
        return jsonify({"ok": True, "roles": roles})
    except Exception as e:
        # We give the error text as is, without the trace
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp", "register", "init_app"]
# c=a+b