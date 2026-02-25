# -*- coding: utf-8 -*-
"""Alias-registratsiya dlya mem_kg_routes s zaschitoy ot konfliktov endpoint.

Mosty:
- Yavnyy: (Alias ↔ Realnye routey) - probuem ester.routes.mem_kg_routes i routes.mem_kg_routes.
- Skrytyy #1: (Registratsiya ↔ Ostorozhnost) — guard podavlyaet dubli endpoint i otsutstvie view_func.
- Skrytyy #2: (Kontrakty ↔ Sovmestimost) — soblyudaem drop-in: snachala reg(app), inache blueprint.

Zemnoy abzats:
Kak “razvetvitel na DIN-reyku”: stavim bez perepayki, ne meshaya suschestvuyuschim liniyam.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint
from .register_guard_alias import import_route_module, with_guard_if_B
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register_mem_kg_routes_alias(app, url_prefix: str = "/mem"):
    mod = import_route_module("ester.routes.mem_kg_routes", "routes.mem_kg_routes")
    if not mod:
        return

    def do_register():
        reg = getattr(mod, "register", None) or getattr(mod, "register_mem_kg_routes", None)
        if callable(reg):
            try:
                reg(app)
                return
            except Exception as e:
                if getattr(app, "logger", None):
                    app.logger.warning("mem_kg_routes_alias: original register failed: %s", e)

        bp = getattr(mod, "mem_bp", None) or getattr(mod, "bp", None)
        if isinstance(bp, Blueprint):
            if bp.name in app.blueprints:
                return
            app.register_blueprint(bp, url_prefix=url_prefix)

    with_guard_if_B(app, do_register)

# AUTOSHIM
def register(app):
    return register_mem_kg_routes_alias(app)