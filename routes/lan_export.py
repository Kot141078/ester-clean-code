# -*- coding: utf-8 -*-
"""routes/lan_export.py - endpointy eksporta mini-cataloga uzla v LAN.

Route:
  • GET /_lan/ping - minimalnaya proverka dostupnosti
  • GET /lan/catalog_export - ester.lan.catalog/1 (what u uzla est lokalno)

Zemnoy abzats:
Eto “okontse na sklad”: mozhno postuchatsya (ping) i poluchit opis dostupnogo.

Mosty:
- Yavnyy (Eksport ↔ Sosedi): prostoy HTTP JSON dlya LAN-sinkhronizatsii.
- Skrytyy 1 (Infoteoriya): format unifitsirovan s USB-catalogom.
- Skrytyy 2 (Praktika): stdlib/Flask, offflayn.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.lan_catalog.exporter import build_local_catalog  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lanexp = Blueprint("lan_export", __name__)

@bp_lanexp.get("/_lan/ping")
def ping():
    obj = build_local_catalog({})
    return jsonify({"ok": True, "node": obj.get("node"), "base_url": obj.get("base_url")})

@bp_lanexp.get("/lan/catalog_export")
def catalog_export():
    return jsonify(build_local_catalog({}))

def register_lan_export(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lanexp)
# c=a+b


def register(app):
    app.register_blueprint(bp_lanexp)
    return app