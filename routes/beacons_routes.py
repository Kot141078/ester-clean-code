# routes/beacons_routes.py
# -*- coding: utf-8 -*-
"""
routes/beacons_routes.py — REST-ручки для просмотра маяков (beacons) активности.

Эндпойнты (JWT):
  GET  /beacons/list?limit=200&since=<ts>&kinds=backup.done,scheduler:tick
  GET  /beacons/stats?limit=1000&since=<ts>

Р егистрация:
  from routes.beacons_routes import register_beacons_routes
  register_beacons_routes(app, url_prefix="/beacons")
"""
from __future__ import annotations

from typing import List, Optional

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules.kg_beacons_query import beacons_stats, list_beacons


def register_beacons_routes(app, url_prefix: str = "/beacons"):
    @app.get(f"{url_prefix}/list")
    @jwt_required()
    def beacons_list():
        try:
            limit = int(request.args.get("limit") or 200)
        except Exception:
            limit = 200
        kinds_param = (request.args.get("kinds") or "").strip()
        kinds: Optional[List[str]] = None
        if kinds_param:
            kinds = [s.strip() for s in kinds_param.split(",") if s.strip()]
        try:
            since = request.args.get("since")
            since_ts = float(since) if since is not None else None
        except Exception:
            since_ts = None

        rows = list_beacons(limit=limit, since=since_ts, kinds=kinds)
        return jsonify({"ok": True, "items": rows, "count": len(rows)})

    @app.get(f"{url_prefix}/stats")
    @jwt_required()
    def beacons_stats_view():
        try:
            limit = int(request.args.get("limit") or 1000)
        except Exception:
            limit = 1000
        try:
            since = request.args.get("since")
            since_ts = float(since) if since is not None else None
        except Exception:
            since_ts = None

        data = beacons_stats(limit=limit, since=since_ts)
        return jsonify(data)


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # вызываем существующий register_beacons_routes(app) (url_prefix берётся по умолчанию внутри функции)
    return register_beacons_routes(app)

# === /AUTOSHIM ===
