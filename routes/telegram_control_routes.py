# -*- coding: utf-8 -*-
# routes/telegram_control_routes.py
"""
routes/telegram_control_routes.py — JSON-API upravleniya profilem Telegram-bota.

Prefiks: /tg/ctrl/api
Marshruty:
  • GET  /tg/ctrl/api/get_me         — Informatsiya o bote + tekuschie komandy (JWT: user/admin)
  • POST /tg/ctrl/api/set_profile    — Ustanovit name / short_description / description (JWT: admin)
  • POST /tg/ctrl/api/set_commands   — Ustanovit komandy (JWT: admin)

Zavisimosti:
  • services.telegram_client.TelegramClient

Sovmestimost (drop-in):
  • Puti sovpadayut s temi, chto dergaet shablon templates/telegram_control_ui.html.
  • R egistratsiya blyuprinta vypolnyaetsya v register_all.py (sm. blok s /tg/ctrl).

Zemnoy abzats (inzheneriya):
Chistoe razdelenie obyazannostey: UI — v odnom module, JSON-API — v drugom. Eto snizhaet svyaznost,
uproschaet otladku i isklyuchaet dvoynuyu registratsiyu marshrutov.

Mosty:
- Yavnyy (Kibernetika v†" Arkhitektura): operator v†' kontroller v†' bot (obratnaya svyaz cherez get_me).
- Skrytyy 1 (Infoteoriya v†" Interfeysy): strogiy JSON-kontrakt po Bot API umenshaet entropiyu integratsii.
- Skrytyy 2 (Anatomiya v†" PO): «rechevoy tsentr» (imya/opisaniya/komandy) upravlyaetsya soznatelno Re atomarno.

# c=a+b
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from services.telegram_client import TelegramClient
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# JWT optsionalen
try:
    from flask_jwt_extended import jwt_required, get_jwt  # type: ignore
except Exception:  # pragma: no cover
    jwt_required = None  # type: ignore
    get_jwt = None  # type: ignore

bp = Blueprint("telegram_control_api", __name__, url_prefix="/tg/ctrl/api")

def _has_role(jwt_claims: dict, allowed: set[str]) -> bool:
    roles = jwt_claims.get("roles") or jwt_claims.get("role") or []
    if isinstance(roles, str):
        roles = [roles]
    return bool(set([str(r).lower() for r in roles]) & set([a.lower() for a in allowed]))

# ----------------------------- JSON API -----------------------------

if jwt_required:
    @bp.get("/get_me")
    @jwt_required(optional=True)  # chitat mozhet i user
    def api_get_me():
        try:
            api = TelegramClient()
            me = api.get_me()
            try:
                cmds = api.get_my_commands()
            except Exception as e:
                cmds = {"ok": False, "error": str(e)}
            return jsonify({"ok": True, "me": me, "commands": cmds})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    @bp.post("/set_profile")
    @jwt_required()
    def api_set_profile():
        claims = get_jwt()  # type: ignore
        if not _has_role(claims, {"admin"}):
            return jsonify({"ok": False, "error": "forbidden"}), 403

        data: Dict[str, Any] = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        short_desc = (data.get("short_description") or "").strip()
        desc = (data.get("description") or "").strip()

        api = TelegramClient()
        res: Dict[str, Any] = {"set_name": None, "set_short_description": None, "set_description": None}

        try:
            if name:
                res["set_name"] = api.set_my_name(name=name)
            if short_desc:
                res["set_short_description"] = api.set_my_short_description(short_description=short_desc)
            if desc:
                res["set_description"] = api.set_my_description(description=desc)
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

        return jsonify({"ok": True, "result": res})

    @bp.post("/set_commands")
    @jwt_required()
    def api_set_commands():
        claims = get_jwt()  # type: ignore
        if not _has_role(claims, {"admin"}):
            return jsonify({"ok": False, "error": "forbidden"}), 403

        data: Dict[str, Any] = request.get_json(silent=True) or {}
        commands = data.get("commands")
        # Prinimaem libo spisok obektov, libo textarea-stroku JSON
        if isinstance(commands, str):
            try:
                commands = json.loads(commands)
            except Exception:
                return jsonify({"ok": False, "error": "commands must be JSON list"}), 400
        if not isinstance(commands, list):
            return jsonify({"ok": False, "error": "commands must be list"}), 400

        # Validatsiya prostaya
        clean: List[Dict[str, str]] = []
        for item in commands:
            if not isinstance(item, dict):
                continue
            cmd = str(item.get("command") or "").strip().lstrip("/")
            des = str(item.get("description") or "").strip()
            if cmd and des:
                clean.append({"command": cmd, "description": des})

        if not clean:
            return jsonify({"ok": False, "error": "no valid commands"}), 400

        try:
            api = TelegramClient()
            res = api.set_my_commands(clean)
            return jsonify({"ok": True, "result": res, "count": len(clean)})
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

else:
    # Bez JWT — obyasnyaem prichinu
    @bp.get("/get_me")  # type: ignore[misc]
    def api_get_me_nojwt():
        return jsonify({"ok": False, "error": "jwt_required_unavailable"}), 503

    @bp.post("/set_profile")  # type: ignore[misc]
    def api_set_profile_nojwt():
        return jsonify({"ok": False, "error": "jwt_required_unavailable"}), 503

    @bp.post("/set_commands")  # type: ignore[misc]
    def api_set_commands_nojwt():
        return jsonify({"ok": False, "error": "jwt_required_unavailable"}), 503

def register_telegram_control_routes(app) -> None:
    """Sovmestimyy imenovannyy registrator dlya starykh vyzovov."""
    if bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp)



def register(app):
    register_telegram_control_routes(app)
    return app
