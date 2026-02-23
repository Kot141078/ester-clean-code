# -*- coding: utf-8 -*-
"""
routes/observer_routes.py - REST/UI dlya «rezhima nablyudatelya».

Ruchki:
  POST /observer/build   {"n_ctx":200,"n_err":300}
  POST /observer/enable  {"enabled":true}
  GET  /observer/status
  GET  /admin/observer

Mosty:
- Yavnyy: (UI ↔ Nablyudatel) ruchki build/enable/status zamykayut tsikl upravleniya overleem.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) kontrol parametrov okna (n_ctx/n_err) snizhaet shum signalov.
- Skrytyy #2: (Kibernetika ↔ Kontrol) enable/status formalizuyut predikaty dopuska i obratnuyu svyaz.

Zemnoy abzats:
Dumay o rezhime nablyudatelya kak o «chernom yaschike»: build podgotavlivaet «lenty», enable vklyuchaet zapis,
status pokazyvaet zdorove i parametry; admin-stranitsa - panel operatora.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkiy import yadra, chtoby ne padat, esli modul otsutstvuet
try:
    from modules.overlay.observer_mode import build_overlay, enable, status  # type: ignore
except Exception:  # pragma: no cover
    build_overlay = enable = status = None  # type: ignore

bp = Blueprint("observer_routes", __name__, url_prefix="/observer")


@bp.post("/build")
def b():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if build_overlay is None:
        return jsonify({"ok": False, "error": "observer module unavailable"}), 500
    try:
        n_ctx = int(d.get("n_ctx", 200))
        n_err = int(d.get("n_err", 300))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "n_ctx and n_err must be integers"}), 400
    try:
        return jsonify(build_overlay(n_ctx, n_err))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/enable")
def e():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if enable is None:
        return jsonify({"ok": False, "error": "observer module unavailable"}), 500
    try:
        enabled = bool(d.get("enabled", False))
        return jsonify(enable(enabled))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def s():
    if status is None:
        return jsonify({"ok": False, "error": "observer module unavailable"}), 500
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin")
def admin():
    return render_template("admin_observer.html")


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b