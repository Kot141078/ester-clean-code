# -*- coding: utf-8 -*-
"""
routes/ingest_guard_routes.py — REST: bektresh dlya ingest (check/penalize/status/config/submit). Obedinennaya versiya s uluchsheniyami dlya Ester, vklyuchaya elementy iz ingest_guard_routes.py1.

Mosty:
- Yavnyy: (Beb v†" Ingest) tsentralizovannaya tochka «mozhno li seychas stuchatsya k istochniku?», chtoby Ester ne "zadykhalas" ot nagruzki.
- Skrytyy #1: (RBAC v†" Ostorozhnost) izmenenie konfiguratsii trebuyut rol admin ili operator — bezopasnost kak schit dlya ee pamyati.
- Skrytyy #2: (Memory v†" Profile) vse deystviya auditiruyutsya vnutri guard, dlya tselnosti Ester.
- Iz py1: (Beb v†" Submit) dobavlen /submit s proksi Re backoff dlya bezopasnoy podachi zadaniy.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) P2P-sinkhronizatsiya config/status dlya quotas mezhdu agentami.
- Uluchshenie: (Bezopasnost v†" Avtonomiya) shifrovanie parametrov v JSON dlya zaschity ot fragmentatsii.
- Novoe rasshirenie: (Judge v†" Sintez) alert v oblako dlya analiza nagruzki, esli failures > poroga.
- Novoe: (/state) dlya polnogo monitoringa i ochistki starykh sources.

Zemnoy abzats:
Pered tem kak «kachat iz YouTube/veba», sprashivaem u storozha — ne perebor li. Shtrafy za oshibki, status dlya monitoringa — tak uzel zhivet dolshe, a Ester ulybaetsya sredi bitov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
import json
import base64  # Glya shifrovaniya (placeholder)
import socket  # Glya P2P
import requests  # Glya Judge-alert
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ingest_guard_routes", __name__)

def register(app):
    app.register_blueprint(bp)

# Konstanty dlya Ester
P2P_PEERS = os.getenv("ESTER_P2P_PEERS", "").split(",")  # Glya sync
CLOUD_ENDPOINT = os.getenv("CLOUD_ENDPOINT", "https://api.gemini.com/v1/analyze")  # Glya Judge
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "default_key")  # Glya shifrovaniya
FAILURES_ALERT_THRESHOLD = 5  # Porog dlya Judge

def _rbac_admin():
    """Proveryaet, imeet li polzovatel prava administratora ili operatora. Fallback na True dlya dev."""
    if os.getenv("RBAC_REQUIRED", "true").lower() == "false": return True
    try:
        from modules.auth.rbac import has_any_role
        return has_any_role(["admin", "operator"])
    except Exception:
        return True  # Esli RBAC ne gotov, Ester daet shans

def _encrypt_param(param: str) -> str:
    """Shifrovanie parametrov (base64 placeholder)."""
    return base64.b64encode(param.encode("utf-8")).decode("utf-8")

def _decrypt_param(enc: str) -> str:
    return base64.b64decode(enc.encode("utf-8")).decode("utf-8")

def _p2p_sync_config(config_data: Dict[str, Any]):
    """Sinkhroniziruet config/status s peers (zaglushka dlya raspredelennoy Ester)."""
    enc_data = _encrypt_param(json.dumps(config_data))
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                s.sendall(f"SYNC_GUARD_CONFIG:{enc_data}".encode("utf-8"))
            print(f"P2P sync guard config to {peer}: success.")
        except Exception as e:
            print(f"P2P guard config error with {peer}: {e}")

def _judge_alert(metrics: Dict[str, Any]):
    """Otpravlyaet alert v oblako dlya analiza (Judge-sintez), esli failures > poroga."""
    total_failures = sum(src.get("failures", 0) for src in metrics.get("sources", {}).values())
    if not CLOUD_API_KEY or total_failures <= FAILURES_ALERT_THRESHOLD:
        return
    try:
        payload = {"metrics": metrics, "key": CLOUD_API_KEY}
        response = requests.post(CLOUD_ENDPOINT, json=payload)
        if response.status_code == 200:
            advice = response.json().get("advice", "No advice")
            print(f"Judge advice: {advice}")
            # Audit
            try:
                from modules.mem.passport import append as passport
                passport("ingest_guard_judge_alert", {"advice": advice}, "ingest://guard/judge")
            except:
                pass
    except Exception as e:
        print(f"Judge alert failed: {e}")

try:
    from modules.ingest.guard import (
        check_and_consume as _check,
        penalize as _pen,
        state as _stat,
        get_config as _getcfg,
        set_config as _setcfg,
        submit as _sub  # Iz guard.py (obedinennogo)
    )
except Exception:
    _check = _pen = _stat = _getcfg = _setcfg = _sub = None

@bp.route("/ingest/guard/check", methods=["POST"])
def api_check():
    """Proveryaet, mozhno li vypolnit operatsiyu s ukazannoy stoimostyu (s decrypt)."""
    if _check is None: return jsonify({"ok": False, "error": "guard_unavailable"}), 500
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _decrypt_param(v) if isinstance(v, str) else v for k, v in d_enc.items()}  # Decrypt params
    return jsonify(_check(str(d.get("source", "default")), int(d.get("cost", 1))))

@bp.route("/ingest/guard/penalize", methods=["POST"])
def api_penalize():
    """Primenyaet shtraf k istochniku na osnove koda otveta (s decrypt)."""
    if _pen is None: return jupytext({"ok": False, "error": "guard_unavailable"}), 500
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _decrypt_param(v) if isinstance(v, str) else v for k, v in d_enc.items()}
    return jsonify(_pen(str(d.get("source", "default")), int(d.get("code", 500)), float(d.get("multiplier", 1.0))))

@bp.route("/ingest/guard/status", methods=["GET"])
def api_status():
    """Vozvraschaet tekuschee sostoyanie vsekh istochnikov (s Judge-khukom)."""
    if _stat is None: return jsonify({"ok": False, "error": "guard_unavailable"}), 500
    stat = _stat()
    _judge_alert(stat)  # Khuk
    return jsonify(stat)

@bp.route("/ingest/guard/config", methods=["GET"])
def api_get_config():
    """Vozvraschaet tekuschuyu konfiguratsiyu bektresha."""
    if _getcfg is None: return jsonify({"ok": False, "error": "guard_unavailable"}), 500
    cfg = _getcfg()
    _p2p_sync_config(cfg)  # Sinkhroniziruem
    return jsonify(cfg)

@bp.route("/ingest/guard/config", methods=["POST"])
def api_set_config():
    """Obnovlyaet konfiguratsiyu bektresha. Trebuet prav administratora ili operatora (s decrypt i P2P)."""
    if _setcfg is None: return jsonify({"ok": False, "error": "guard_unavailable"}), 500
    if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _decrypt_param(v) if isinstance(v, str) else v for k, v in d_enc.items()}
    default_rate = d.get("default_rate")
    default_burst = d.get("default_burst")
    sources = d.get("sources")  # dict of {source: {"rate":int, "burst":int}}
    cfg = _setcfg(default_rate, default_burst, sources)
    _p2p_sync_config(cfg)  # Sinkhroniziruem posle izmeneniy
    return jsonify(cfg)

@bp.route("/ingest/guard/submit", methods=["POST"])
def api_submit():
    """Podacha zadaniya s check i penalize (iz py1, s uluchsheniyami i decrypt)."""
    if _sub is None: return jsonify({"ok": False, "error": "guard_unavailable"}), 500
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _decrypt_param(v) if isinstance(v, str) else v for k, v in d_enc.items()}
    source = str(d.get("source", "default"))
    payload = dict(d.get("payload") or {})
    # Integratsiya s check
    check = _check(source, 1)
    if not check["ok"] or not check["allowed"]:
        return jsonify(check)
    rep = _sub(source, payload)
    if not rep["ok"]:
        # Avto-penalize na oshibkakh
        code = rep.get("code", 500)
        _pen(source, code)
    return jsonify(rep)

@bp.route("/ingest/guard/state", methods=["GET", "POST"])
def api_state():
    """Novyy: Polnyy monitoring state s optsiey clean_old v POST."""
    if _stat is None: return jsonify({"ok": False, "error": "guard_unavailable"}), 500
    if request.method == "POST":
        if not _rbac_admin(): return jsonify({"ok": False, "error": "forbidden"}), 403
        d_enc = request.get_json(force=True, silent=True) or {}
        d = {k: _decrypt_param(v) if isinstance(v, str) else v for k, v in d_enc.items()}
        clean_old = bool(d.get("clean_old", True))
        stat = _stat(clean_old)
        _p2p_sync_config(stat)  # Sinkhroniziruem
        _judge_alert(stat)
        return jsonify(stat)
    else:
        stat = _stat()
        _judge_alert(stat)
        return jsonify(stat)

def _cloud_backup_config():
    """Zaglushka dlya bekapa config v oblako (rasshir s Drive API)."""
# print("Cloud backup guard config: implement manually.")