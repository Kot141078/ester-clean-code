# -*- coding: utf-8 -*-
"""Admin Judge - panel request and agregatsii otvetov.

Most (yavnyy):
- (Kibernetika ↔ UX) Polzovatel vidit chernovye otvety modeley i finalnuyu “sborku”.

Mosty (skrytye):
- (Infoteoriya ↔ Ekonomika) Edinyy format vyvoda (answers[], final) snizhaet trenie na sleduyuschikh stadiyakh payplayna i zatraty na routetizatsiyu.
- (Logika ↔ Nadezhnost) A/B-predokhranitel: A=moki, B=realnye lokalnye zaprosy (esli nayden alias).

Zemnoy abzats:
Stranitsa pozvolyaet offlayn (A) validirovat logiku “sudi”, a v B - obraschatsya k lokalnym instansam LM Studio, ne zatragivaya myshlenie/pamyat/volyu Ester: eto instrument vzaimodeystviya."""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, render_template, request

# We do not change contracts: import as in dump
from modules.judge.core import judge, MODE_LOCAL, MODE_FULL, MODE_FLEX  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_judge", __name__, url_prefix="/admin/judge")

# A/B slot for secure self-editing
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()


@bp.get("/")
def page():
    return render_template("admin_judge.html", ab_mode=AB_MODE)


@bp.post("/run")
def api_run():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "").strip()
    mode = str(data.get("mode") or MODE_LOCAL).strip().lower()
    timeout = float(data.get("timeout") or 6.0)

    if not prompt:
        return jsonify({"ok": False, "error": "empty-prompt", "ab": AB_MODE}), 400

    try:
        res = judge(prompt, mode=mode, timeout=timeout)
        return jsonify(res)
    except Exception as e:
        # Drop-in behavior: give an error using ZhSON, without a route
        return jsonify({"ok": False, "error": str(e), "ab": AB_MODE}), 500


def register(app):  # pragma: no cover
    """Blueprint registration (drop-in)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]