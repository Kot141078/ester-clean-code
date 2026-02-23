# -*- coding: utf-8 -*-
"""
routes/usb_agent_tuning.py — panel nastroyki «umnogo» USB-skanirovaniya.

Marshruty:
  • GET  /admin/usb/agent/tuning            — HTML
  • GET  /admin/usb/agent/tuning/status     — JSON: konfig + otsenka intervala + pitanie
  • POST /admin/usb/agent/tuning/save       — zadat rezhim/parametry (persist v STATE_DIR)

Mosty:
- Yavnyy (Kibernetika v†" UX): odin ekran — vybrat rezhim, uvidet otsenku, sokhranit.
- Skrytyy 1 (Infoteoriya v†" Prozrachnost): pokazyvaem sostoyanie pitaniya Re raschet intervala.
- Skrytyy 2 (Praktika v†" Sovmestimost): vklyuchenie smart-drayvera delaetsya cherez avtozapusk (ustanovit/pereustanovit).

Zemnoy abzats:
R egulyator «Eko/Balans/Bystro» — polzovatel vybiraet, a dalshe umnyy drayver sam podstraivaet chastotu obkhodov.

# c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, render_template, request

from modules.selfmanage.usb_tuning_state import load_tuning, save_tuning  # type: ignore
from modules.selfmanage.power_sense import power_status  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_usb_tuning = Blueprint("usb_agent_tuning", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

def _estimate_interval(cfg: dict) -> int:
    # Prostaya kopiya evristiki iz drayvera (bez dublirovaniya vsey logiki)
    from listeners.usb_dyn_driver import Tuning, _target_interval  # type: ignore
    on_ac, batt = power_status()
    t = Tuning(
        mode=cfg.get("mode", "balanced"),
        min_s=int(cfg.get("min_s", 3)),
        max_s=int(cfg.get("max_s", 45)),
        ac_boost=float(cfg.get("ac_boost", 0.5)),
        poll=10
    )
    return _target_interval(t, on_ac, batt)

@bp_usb_tuning.get("/admin/usb/agent/tuning")
def page():
    return render_template("usb_agent_tuning.html", ab=AB)

@bp_usb_tuning.get("/admin/usb/agent/tuning/status")
def api_status():
    cfg = load_tuning()
    on_ac, batt = power_status()
    return jsonify({
        "ok": True,
        "ab": AB,
        "config": cfg,
        "power": {"on_ac": on_ac, "battery_percent": batt},
        "estimated_interval": _estimate_interval(cfg),
        "hint": "Chtoby rezhim primenilsya pri starte sistemy, pereustanovi avtozapusk v /admin/usb/autostart (v B-rezhime)."
    })

@bp_usb_tuning.post("/admin/usb/agent/tuning/save")
def api_save():
    data = request.get_json(silent=True) or {}
    cfg = save_tuning({
        "mode": data.get("mode"),
        "min_s": data.get("min_s"),
        "max_s": data.get("max_s"),
        "ac_boost": data.get("ac_boost"),
    })
    return jsonify({"ok": True, "config": cfg})
    

def register_usb_agent_tuning(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_usb_tuning)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("usb_agent_tuning_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/usb/agent/tuning")
        def _p():
            return page()

        @pref.get("/admin/usb/agent/tuning/status")
        def _ps():
            return api_status()

        @pref.post("/admin/usb/agent/tuning/save")
        def _sv():
            return api_save()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_usb_tuning)
    return app