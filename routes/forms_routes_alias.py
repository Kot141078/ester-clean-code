# -*- coding: utf-8 -*-
"""Alias-registratsiya dlya forms_routes s zaschitoy ot konfliktov endpoint.

Mosty:
- Yavnyy: (Alias ↔ Realnye routey) - try ester.routes.forms_routes i routes.forms_routes.
- Skrytyy #1: (Registratsiya ↔ Ostorozhnost) — guard podavlyaet dubli endpoint i otsutstvie view_func.
- Skrytyy #2: (Kontrakty ↔ Sovmestimost) — soblyudaem drop-in: snachala reg(app), inache blueprint.

Zemnoy abzats:
Eto “servisnyy troynik”: esli shtatnyy razem est - vklyuchaemsya tuda; esli net - berem universalnyy perekhodnik.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint
from .register_guard_alias import import_route_module, with_guard_if_B
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register_forms_routes_alias(app, url_prefix: str = "/forms"):
    mod = import_route_module("ester.routes.forms_routes", "routes.forms_routes")
    if not mod:
        # nothing to register - leaves quietly
        return

    def do_register():
        # 1) Trying the standard registration function
        reg = getattr(mod, "register", None) or getattr(mod, "register_forms_routes", None)
        if callable(reg):
            try:
                reg(app)  # trust the original, guard to intercept conflicts with B
                return
            except Exception as e:
                # Padat ne daem — poprobuem blueprint nizhe
                if getattr(app, "logger", None):
                    app.logger.warning("forms_routes_alias: original register failed: %s", e)

        # 2) Probuem blueprint
        bp = getattr(mod, "forms_bp", None) or getattr(mod, "bp", None)
        if isinstance(bp, Blueprint):
            # if such a blue print already exists, we do not register it a second time
            if bp.name in app.blueprints:
                return
            app.register_blueprint(bp, url_prefix=url_prefix)
            return

    with_guard_if_B(app, do_register)

# AUTOSHIM
def register(app):
    return register_forms_routes_alias(app)