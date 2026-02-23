# -*- coding: utf-8 -*-
"""
routes/lan_catalog.py - UI/REST dlya kataloga uzlov LAN.

Marshruty:
  • GET  /admin/lan/catalog            - HTML
  • GET  /admin/lan/catalog/status     - snimok self/peers + podskazki (ARP)
  • POST /admin/lan/catalog/rescan     - mgnovennyy beacon + ARP-reskan

Mosty:
- Yavnyy (UX ↔ Kibernetika): «radar» s zhivym spiskom istochnikov.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): TTL, versiya i score vidny polzovatelyu.
- Skrytyy 2 (Praktika ↔ Sovmestimost): nichego ne menyaem v yadre; tolko infrastrukturnyy obzor.

Zemnoy abzats:
Eto «ekran radara»: kto v seti, kakie versii i kuda stuchatsya, chtoby zabrat portativnyy slot.

# c=a+b
"""
from __future__ import annotations
import json, os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.lan.catalog_settings import load_catalog_settings, save_catalog_settings  # type: ignore
from modules.lan.catalog import pick_sources, arp_rescan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
STATE = STATE_DIR / "lan_catalog_state.json"

bp_lanc = Blueprint("lan_catalog", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _load_json(p: Path):
    try:
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception: pass
    return {}

@bp_lanc.get("/admin/lan/catalog")
def page():
    return render_template("lan_catalog.html", ab=AB)

@bp_lanc.get("/admin/lan/catalog/status")
def status():
    s = load_catalog_settings()
    st = _load_json(STATE)
    src = pick_sources()
    return jsonify({"ok": True, "ab": AB, "settings": s, "state": st, "sources": src, "arp": arp_rescan()[:32]})

@bp_lanc.post("/admin/lan/catalog/rescan")
def rescan():
    # bystryy mayak - listener ego podberet; ARP dlya polzovatelya
    from modules.lan.catalog import beacon_once  # type: ignore
    beacon_once(load_catalog_settings())
    return jsonify({"ok": True, "arp": arp_rescan()[:32]})

def register_lan_catalog(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lanc)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_catalog_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lan/catalog")
        def _p(): return page()

        @pref.get("/admin/lan/catalog/status")
        def _s(): return status()

        @pref.post("/admin/lan/catalog/rescan")
        def _r(): return rescan()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lanc)
    return app