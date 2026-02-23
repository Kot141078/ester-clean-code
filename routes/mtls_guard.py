# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/mtls_guard.py - REST: /mtls/whoami
Vozvraschaet svedeniya o «mTLS-lichnosti» zaprosa na osnove zagolovkov ot ingress.

Ozhidaemye zagolovki:
  - X-Client-Verified: SUCCESS  (inache mTLS schitaem neuspeshnym)
  - X-Client-DN: polnaya DN-stroka klientskogo sertifikata (naprimer, "CN=alice,O=Acme,OU=R&D")

Kontrakty:
  GET /mtls/whoami -> {"ok":true,"verified":bool,"dn":str,"role":str|null,"hint":str}

# c=a+b
"""

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkiy import role-map (kontrakty ne lomaem)
try:
    from security.mtls_rolemap import map_dn_to_role  # type: ignore
except Exception:  # pragma: no cover
    map_dn_to_role = None  # type: ignore

bp_mtls = Blueprint("mtls_guard", __name__, url_prefix="/mtls")


@bp_mtls.get("/whoami")
def mtls_whoami():
    """
    Vozvraschaet informatsiyu o mTLS-identichnosti zaprosa.
    Role vychislyaetsya po rules/mtls_roles.yaml cherez security.mtls_rolemap.
    """
    verified = (request.headers.get("X-Client-Verified") or "").upper() == "SUCCESS"
    dn = request.headers.get("X-Client-DN", "")
    role = map_dn_to_role(dn) if (verified and map_dn_to_role) else None
    return jsonify(
        {
            "ok": True,
            "verified": verified,
            "dn": dn,
            "role": role,
            "hint": "Provide X-Client-Verified: SUCCESS and X-Client-DN via ingress after mTLS.",
        }
    )


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp_mtls)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp_mtls", "register", "init_app"]
# c=a+b