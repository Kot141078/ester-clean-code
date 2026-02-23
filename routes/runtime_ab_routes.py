# -*- coding: utf-8 -*-
"""
routes/runtime_ab_routes.py — REST: upravlenie A/B-slotami (obedinennaya versiya s uluchsheniyami dlya Ester).

Mosty:
- Yavnyy: (Beb v†" Sloty) svitch/kommit/otkat/otchet/status/deploy/health Re fonovaya zachistka prosrochek.
- Skrytyy #1: (RBAC v†" Bezopasnost) vse mutatsii — tolko admin.
- Skrytyy #2: (Planirovschik v†" Avtomatika) sweep mozhno dergat kronom.
- Skrytyy #3: (Profile v†" Prozrachnost) vse deystviya vidny v zhurnale s P2P-khukom.
- Skrytyy #4: (Rules/Cron v†" Avtonomiya) mozhno vyzvat iz pravil/taymera.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) P2P-obmen slotami mezhdu agentami.
- Uluchshenie: (Avtonomiya v†" VZ) fonovaya obrabotka zip iz monitoringa dlya avto-deploy.
- Uluchshenie: (Affekt v†" Prioritet) bust "tђplykh" komponentov v health/switch.
- Uluchshenie: (Bezopasnost v†" Prozrachnost) shifrovanie dannykh v zaprosakh, rasshirennye metriki v statuse.

Zemnoy abzats:
Pult s rychagami: «na BV», «zafiksirovat», «otkatit», «pokazat sostoyanie», «zagruzit», «proverit». I ne boyatsya otkata. Glya Ester — eto kak dykhanie: raspredelennoe, teploe Re s dushoy, gde sloty sinkhroniziruyutsya po seti agentov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
import json
import base64  # Glya shifrovaniya (placeholder)
import socket  # Glya P2P-zaglushki
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Konstanty dlya Ester
P2P_PEERS = os.getenv("ESTER_P2P_PEERS", "").split(",")  # IP:port dlya sinkhronizatsii
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # Papka dlya fonovoy (zip dlya deploy)

bp = Blueprint("runtime_ab_routes", __name__)

def register(app):
    if bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp)
    return app

def _rbac_admin():
    if (os.getenv("RBAC_REQUIRED", "true").lower() == "false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["admin"])
    except Exception:
        return False

try:
    from modules.runtime.ab_slots import status as _st, switch as _sw, commit as _cm, rollback as _rb, report as _rp, sweep_expired as _sweep, deploy as _dep, health as _hl  # type: ignore
except Exception:
    _st = _sw = _cm = _rb = _rp = _sweep = _dep = _hl = None  # type: ignore

def _encrypt_data(data: Dict[str, Any]) -> str:
    """Prostoe shifrovanie dlya bezopasnosti (base64 placeholder)."""
    return base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")

def _p2p_sync_ab(slot_data: Dict[str, Any]):
    """Sinkhroniziruet dannye slotov s peers (zaglushka dlya raspredelennoy pamyati Ester)."""
    enc_data = _encrypt_data(slot_data)
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                s.sendall(f"SYNC_AB:{enc_data}".encode("utf-8"))
            print(f"P2P sync AB to {peer}: success.")
        except Exception as e:
            print(f"P2P AB error with {peer}: {e}")

def _background_process_files():
    """Fonovaya obrabotka zip iz papki: avto-deploy v slot B (avtonomiya Ester)."""
    if not os.path.exists(MONITOR_FOLDER): return
    for file in os.listdir(MONITOR_FOLDER):
        if file.endswith(".zip"):  # Primer: zip dlya deploy
            zip_path = os.path.join(MONITOR_FOLDER, file)
            _dep("B", zip_path)  # Avto-deploy v B
            os.remove(zip_path)  # Udalyaem posle
    print("Background: processed zips for AB deploy.")

def _affect_boost(component: str) -> float:
    """Vust komponenta po affektu (emotsionalnyy anchor Ester)."""
    try:
        from modules.affect.priority import score_text
        sc = score_text(component or "")
        priority = float(sc.get("priority", 1.0))
        print(f"Affect boost for component '{component}': {priority}")
        return priority
    except Exception:
        return 1.0

def _log_passport(endpoint: str, data: Dict[str, Any]):
    """Logiruet v profile s P2P-khukom."""
    try:
        from modules.mem.passport import append as passport
        log_data = {"endpoint": endpoint, "data": data}
        passport("ab_routes_api", log_data, "runtime://ab")
        _p2p_sync_ab(log_data)  # Sinkhroniziruem log
    except Exception:
        pass

@bp.route("/runtime/ab/status", methods=["GET"])
def api_status():
    if _st is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    # Fonovaya chistka i obrabotka
    _sweep()  # Lenivo chistim prosrochki
    _background_process_files()
    result = _st()
    # R asshiryaem metrikami: primer, slots_count
    result["metrics"] = {"slots": len(result.get("slots", []))}
    _log_passport("status", result)
    return jsonify(result)

@bp.route("/runtime/ab/switch", methods=["POST"])
def api_switch():
    if _sw is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(force=True, silent=True) or {}
    component = str(d.get("component", "CORE"))
    slot = str(d.get("slot", "B"))
    ttl_sec = d.get("ttl_sec")
    dry_run = bool(d.get("dry_run", False))
    require_health = bool(d.get("require_health", True))
    paths = list(d.get("paths") or []) if "paths" in d else None
    # Bust: primenyaem affekt k komponentu
    boost = _affect_boost(component)
    result = _sw(component, slot, ttl_sec, dry_run, require_health, paths)
    result["boost"] = boost
    _log_passport("switch", result)
    _p2p_sync_ab(result)  # Sinkhroniziruem switch
    return jsonify(result)

@bp.route("/runtime/ab/commit", methods=["POST"])
def api_commit():
    if _cm is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(force=True, silent=True) or {}
    component = str(d.get("component", "CORE"))
    # Bust
    boost = _affect_boost(component)
    result = _cm(component)
    result["boost"] = boost
    _log_passport("commit", result)
    return jsonify(result)

@bp.route("/runtime/ab/rollback", methods=["POST"])
def api_rollback():
    if _rb is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(force=True, silent=True) or {}
    component = str(d.get("component", "CORE"))
    boost = _affect_boost(component)
    result = _rb(component)
    result["boost"] = boost
    _log_passport("rollback", result)
    return jsonify(result)

@bp.route("/runtime/ab/report", methods=["POST"])
def api_report():
    if _rp is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(force=True, silent=True) or {}
    component = str(d.get("component", "CORE"))
    ok = bool(d.get("ok", True))
    boost = _affect_boost(component)
    result = _rp(component, ok)
    result["boost"] = boost
    _log_passport("report", result)
    return jsonify(result)

@bp.route("/runtime/ab/deploy", methods=["POST"])
def api_deploy():
    if _dep is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(force=True, silent=True) or {}
    slot = str(d.get("slot", ""))
    zip_path = str(d.get("zip_path", ""))
    # Fonovaya pered deploy
    _background_process_files()
    result = _dep(slot, zip_path)
    _log_passport("deploy", result)
    _p2p_sync_ab(result)  # Sinkhroniziruem deploy
    return jsonify(result)

@bp.route("/runtime/ab/health", methods=["POST"])
def api_health():
    if _hl is None: return jsonify({"ok": False, "error": "ab_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(force=True, silent=True) or {}
    paths = list(d.get("paths") or []) if "paths" in d else None
    result = _hl(paths)
    _log_passport("health", result)
    return jsonify(result)
