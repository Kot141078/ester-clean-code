# routes/diag_ok_routes.py
from __future__ import annotations
import json
from flask import Blueprint, Response, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("_diag_ok", __name__, url_prefix="/_diag")

@bp.route("/ping", methods=["GET"])
def ping() -> Response:
    # Minimalnyy plain-text; guard obychno ne trogaet tekstovye 200.
    return Response("pong", status=200, headers={"Content-Type": "text/plain; charset=utf-8"})

@bp.route("/json", methods=["GET"])
def json_ok() -> Response:
    # Ruchnoy JSON bez jsonify, chtoby isklyuchit vliyanie provaydera.
    payload = {"ok": True, "note": "Privet, kirillitsa vidna? Ester testiruet UTF-8."}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return Response(body, status=200, headers={"Content-Type": "application/json; charset=utf-8"})

@bp.route("/echo", methods=["POST"])
def echo() -> Response:
    try:
        data = request.get_data(cache=False)  # syrye bayty
        # Vozvraschaem kak est, no pomechaem UTF-8 - klient pokazhet pravilno.
        return Response(data, status=200, headers={"Content-Type": "application/json; charset=utf-8"})
    except Exception as e:
        body = json.dumps({"ok": False, "err": str(e)}, ensure_ascii=False)
        return Response(body, status=500, headers={"Content-Type": "application/json; charset=utf-8"})

def register(app):
    app.register_blueprint(bp)
    try:
        app.logger.info("diag_ok_routes: registered /_diag/*")
    except Exception:
        pass