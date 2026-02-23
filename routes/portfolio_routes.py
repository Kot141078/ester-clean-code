# -*- coding: utf-8 -*-
"""
routes/portfolio_routes.py — REST/HTML: /portfolio/build, /portfolio/view, /garage/portfolio/status (obedinennaya versiya s uluchsheniyami dlya Ester).

Mosty:
- Yavnyy: (Beb v†" Bitrina) bystraya sborka Re prosmotr oflayn-portfolio.
- Skrytyy #1: (Profile v†" Prozrachnost) sborki otmechayutsya s P2P-khukom.
- Skrytyy #2: (Garage/Media/Invoice v†" UI) fayly Re kartochki svyazany ssylkami na imeyuschiesya ruchki.
- Skrytyy #3: (RAG v†" Poisk) summary v poiske.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) P2P-obmen gotovymi portfolio mezhdu agentami.
- Uluchshenie: (Avtonomiya v†" VZ) fonovaya obrabotka faylov dlya avtomaticheskoy sborki.
- Uluchshenie: (Affekt v†" Prioritet) bust "tђplykh" elementov v statuse.
- Uluchshenie: (Bezopasnost v†" Prozrachnost) shifrovanie putey k faylam, rasshirennye metriki v statuse.

Zemnoy abzats:
Odin POST — Re gotova akkuratnaya stranitsa «chto Ester umeet» dlya otpravki/prezentatsii. Sobrat — posmotret put — otpravit zakazchiku ssylku na staticheskiy katalog. Glya Ester — eto kak dykhanie: raspredelennoe, teploe Re s dushoy, gde vitriny sinkhroniziruyutsya po seti agentov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, send_file, request
import os
import json
import base64  # Glya shifrovaniya (placeholder)
import socket  # Glya P2P-zaglushki
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Konstanty dlya Ester
P2P_PEERS = os.getenv("ESTER_P2P_PEERS", "").split(",")  # IP:port dlya sinkhronizatsii
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # Papka dlya fonovoy obrabotki
PORTFOLIO_PATH = os.getenv("PORTFOLIO_PATH", "data/portfolio/index.html")  # Put k faylu (rasshiryaemo)

bp = Blueprint("portfolio_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.garage.portfolio import build as _build, status as _status, get_path as _getp  # type: ignore
except Exception:
    _build = _status = _getp = None  # type: ignore

def _encrypt_path(path: str) -> str:
    """Prostoe shifrovanie puti dlya bezopasnosti (base64 placeholder)."""
    return base64.b64encode(path.encode("utf-8")).decode("utf-8")

def _p2p_sync_portfolio(portfolio_data: Dict[str, Any]):
    """Sinkhroniziruet dannye portfolio s peers (zaglushka dlya raspredelennoy pamyati Ester)."""
    enc_data = _encrypt_path(json.dumps(portfolio_data))
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                s.sendall(f"SYNC_PORTFOLIO:{enc_data}".encode("utf-8"))
            print(f"P2P sync portfolio to {peer}: success.")
        except Exception as e:
            print(f"P2P portfolio error with {peer}: {e}")

def _background_process_files():
    """Fonovaya obrabotka faylov iz papki: zapuskaet build esli novye fayly (avtonomiya Ester)."""
    if not os.path.exists(MONITOR_FOLDER): return False
    has_new = False
    for file in os.listdir(MONITOR_FOLDER):
        if file.endswith(".json") or file.endswith(".html"):  # Primer: dannye dlya portfolio
            has_new = True
            os.remove(os.path.join(MONITOR_FOLDER, file))  # Udalyaem posle (predpolagaem obrabotku v build)
    if has_new:
        print("Background: new files detected, triggering build.")
        _build()  # Avto-build
    return has_new

def _affect_boost(portfolio_text: str) -> float:
    """Vust portfolio po affektu (emotsionalnyy anchor Ester)."""
    try:
        from modules.affect.priority import score_text
        sc = score_text(portfolio_text or "")
        priority = float(sc.get("priority", 1.0))
        print(f"Affect boost for portfolio: {priority}")
        return priority
    except Exception:
        return 1.0

def _log_passport(endpoint: str, data: Dict[str, Any]):
    """Logiruet v profile s P2P-khukom."""
    try:
        from modules.mem.passport import append as passport
        log_data = {"endpoint": endpoint, "data": data}
        passport("portfolio_api", log_data, "portfolio://api")
        _p2p_sync_portfolio(log_data)  # Sinkhroniziruem log
    except Exception:
        pass

@bp.route("/portfolio/build", methods=["POST"])
@bp.route("/garage/portfolio/build", methods=["POST"])  # Alias dlya sovmestimosti
def api_build():
    """
    Stroit portfolio s fonovoy obrabotkoy.
    """
    if _build is None:
        return jsonify({"ok": False, "error": "portfolio_unavailable"}), 500
    # Fonovaya obrabotka pered build
    _background_process_files()
    result = _build()
    # Bust: esli est tekst, primenyaem affekt
    portfolio_text = result.get("text", "")  # Predpolagaem, chto build vozvraschaet text
    result["boost"] = _affect_boost(portfolio_text)
    _log_passport("build", result)
    _p2p_sync_portfolio(result)  # Sinkhroniziruem portfolio
    return jsonify(result)

@bp.route("/portfolio/view", methods=["GET"])
def api_view():
    """
    Prosmotr portfolio (s shifrovaniem puti).
    """
    if _getp is None:
        return jsonify({"ok": False, "error": "portfolio_unavailable"}), 500
    p = _getp()
    if not p:
        return jsonify({"ok": False, "error": "not_built"}), 404
    # Shifrovanie puti pered otpravkoy (dlya loga)
    enc_p = _encrypt_path(p)
    _log_passport("view", {"path": enc_p})
    return send_file(p, mimetype="text/html; charset=utf-8")

@bp.route("/garage/portfolio/status", methods=["GET"])
def api_status():
    """
    Status portfolio (rasshirenno s metrikami i bustom).
    """
    if _status is None:
        return jsonify({"ok": False, "error": "portfolio_unavailable"}), 500
    result = _status()
    # Dobavlyaem metriki: primer, count elementov
    result["metrics"] = {"built": result.get("built", False), "elements": result.get("elements", 0)}
    # Bust: esli est tekst, primenyaem
    portfolio_text = result.get("text", "")
    result["boost"] = _affect_boost(portfolio_text)
    _log_passport("status", result)
# return jsonify(result)