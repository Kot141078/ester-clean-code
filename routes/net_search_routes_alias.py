# -*- coding: utf-8 -*-
"""routes/net_search_routes_alias.py

POST /ester/net/search

Name:
- Dat Ester i operatoru edinyy upravlyaemyy endpoint web-poiska.
- All setevoe obschenie idet tolko cherez etot most.
- Reshenie prinimaet politika + karta avtonomii.

Contrakt request (JSON):
{
  "q": "stroka zaprosa",
  "limit": 5,
  "source": "operator" | "ester"
}

Invariance:
- Ne delaet skrytykh vyzovov: tolko po yavnomu HTTP-request.
- Uchityvaet /ester/autonomy/map, if available.
- Uvazhaet A/B flagi i ESTER_NET_SEARCH_ALLOW_ESTER.
- Ne lezet v kaskad, pamyat i kod napryamuyu.

Mosty:
- Yavnyy: HTTP ↔ google_search_bridge.
- Skrytyy #1: net/search ↔ autonomy/map (by decision).
- Skrytyy #2: net/search ↔ will/plan (mozhno vyzyvat iz zadach voli).

Zemnoy abzats:
This is how vydelennyy terminal operatora svyazi:
esli nikto ne nazhal knopku - tishina, nikakogo fonovogo "zvonka naruzhu"."""

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request, current_app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from engines import google_search_bridge  # type: ignore
except Exception:  # pragma: no cover
    google_search_bridge = None  # type: ignore


def _get_autonomy_snapshot(app) -> Dict[str, Any]:
    client = app.test_client()
    try:
        r = client.get("/ester/autonomy/map")
        if r.status_code == 200:
            data = r.get_json(silent=True) or {}
            # expects either {"autonomy": ZZF0Z}, or just a card
            if "autonomy" in data:
                return data["autonomy"]
            return data
    except Exception:
        pass
    # if there is no card, we assume that the default network is prohibited for ester,
    # but is allowed for the operator during a manual call.
    return {"scope": {"network": False}}


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_net_search_routes", __name__, url_prefix="/ester/net")

    @bp.post("/search")
    def net_search() -> Any:
        if google_search_bridge is None:
            return jsonify(
                {
                    "ok": False,
                    "reason": "bridge_missing",
                }
            ), 500

        try:
            payload: Dict[str, Any] = request.get_json(force=True, silent=False)  # type: ignore
        except Exception as e:  # pragma: no cover
            return jsonify({"ok": False, "reason": f"invalid_json:{e}"}), 400

        q = payload.get("q") or payload.get("query") or ""
        limit = payload.get("limit", 5)
        source = (payload.get("source") or "operator").strip().lower()

        app = current_app._get_current_object()
        autonomy = _get_autonomy_snapshot(app)

        result = google_search_bridge.search(
            query=str(q),
            limit=limit,
            source=source,
            autonomy=autonomy,
        )

        code = 200 if result.get("ok") else 400
        return jsonify(result), code

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-net-search/routes] registered /ester/net/search")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]