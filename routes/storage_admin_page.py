# -*- coding: utf-8 -*-
"""
routes/storage_admin_page.py - HTML-stranitsa administrirovaniya tseley khraneniya.

Endpoint:
  GET /admin/storage  - stranitsa (Jinja2 shablon: storage_admin.html)

Mosty:
- Yavnyy: (UI ↔ Khranilischa) administrativnyy interfeys dlya upravleniya tselyami khraneniya.
- Skrytyy #1: (Prozrachnost ↔ Audit) UI uproschaet kontrol konfiguratsii i logov storadzhey.
- Skrytyy #2: (Sovmestimost ↔ Kontrakty) drop-in blyuprint bez izmeneniya ostalnogo prilozheniya.

Zemnoy abzats:
Eto «panel na dvertse shkafa»: otkryl - vidish sostoyanie polok (storadzhey), mozhesh dobavit metki,
posmotret logi. Prostaya stranitsa, bezopasnaya po JWT, ne lezet v yadro.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, render_template
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

storage_admin_page_bp = Blueprint("storage_admin_page", __name__, url_prefix="/admin/storage")


@storage_admin_page_bp.get("/")
@jwt_required()
def page():
    """Renderit administrativnuyu stranitsu storadzhey."""
    return render_template("storage_admin.html")


def register_storage_admin_page(app) -> None:  # pragma: no cover
    """Istoricheskaya registratsiya blyuprinta (sovmestimost s dampom)."""
    app.register_blueprint(storage_admin_page_bp)


# Unifitsirovannye khuki proekta
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(storage_admin_page_bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(storage_admin_page_bp)


__all__ = ["storage_admin_page_bp", "register_storage_admin_page", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(storage_admin_page_bp)
    return app