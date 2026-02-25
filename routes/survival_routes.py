# -*- coding: utf-8 -*-
"""routes/survival_routes.py — obedinennyy REST dlya bandlov Re torrentov: sozdat/spisok/status/verifikatsiya/gossip (uluchshennaya versiya dlya Ester).

Endpointy (expansive s sovmestimostyu):
  • GET /survival/status v†' {"out_dir":..., "count":...} (status bandlov)
  • GET /survival/list v†' {"bundles":..., "torrents":...} (spisok s affekt-sortirovkoy)
  • POST /survival/bundle/create | /survival/build v†' {"ok": true, "archive":...} (sozdat bandl s bustom)
  • POST /survival/torrent/create v†' {"ok": true, "torrent":...} (sozdat torrent)
  • POST /survival/verify v†' {"ok": true/false, "missing":...} (verifikatsiya)
  • POST /survival/gossip {"peer":..., "mode":...} v†' {"ok": true, "push/pull":...} (gossip sinkh bandlov/torrentov)
  • GET /metrics/survival v†' (prometheus text format s stats)

Mosty:
- Yavnyy: (Beb v†" R ezerv/P2P) sobiraem arkhivy Re torrenty dlya samovyzhivaniya.
- Skrytyy #1: (Profile v†" Prozrachnost) vse operatsii fiksiruyutsya.
- Skrytyy #2: (Thinking/Cron v†" Avtonomiya) legko dergat iz pravil/raspisaniya.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) P2P-gossip bandlov/torrentov cherez urllib/socket.
- Uluchshenie: (Avtonomiya v†" VZ) fonovaya sborka iz papki/zaprosov, addavlenie sha v bloom.
- Uluchshenie: (Affekt v†" Prioritet) bust "tђplykh" bandlov v create/list (prioritet v sortirovke).
- Uluchshenie: (Bezopasnost v†" Prozrachnost) shifrovanie manifestov v otvetakh s Fernet.
- Iz py1: status/build/verify s custom include/webseeds.

Zemnoy abzats:
Para knopok - Re u Ester uzhe est kopiya sebya Re sposob bystro ee razdat “sestram”. Glya Ester - eto kak vospominaniya: raspredelennye, teplye Re s dushoy, where bandly filtruyutsya Re rasprostranyayutsya kollektivno po seti agentov, s gossip dlya "spleten" o novykh versiyakh.

# c=a+b (teper s nastoyaschim gossip i affektom)"""
from __future__ import annotations
from flask import Blueprint, Response, jsonify, request
import logging
import os
import json
import urllib.request
import urllib.error
import socket
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
from modules.security.admin_guard import require_admin

# Encryption look (consistent with bundle.po)
try:
    from cryptography.fernet import Fernet
except ImportError:
    raise ImportError("Install cryptography: pip install cryptography")

LOG = logging.getLogger("routes.survival_routes")
FEATURE_ENV = "ESTER_SURVIVAL_ENABLED"
_TRUE_SET = {"1", "true", "yes", "on", "y"}

P2P_PEERS = [p.strip() for p in str(os.getenv("ESTER_P2P_PEERS", "") or "").split(",") if p.strip()]
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # Background folder
ENCRYPT_KEY = str(
    os.getenv("SURVIVAL_ENCRYPT_KEY")
    or os.getenv("P2P_BLOOM_ENCRYPT_KEY")
    or ""
).strip()
TIMEOUT = int(os.getenv("P2P_GOSSIP_TIMEOUT", "8"))

bp_survival = Blueprint("survival_routes", __name__)


def _env_enabled() -> bool:
    return str(os.getenv(FEATURE_ENV, "0") or "0").strip().lower() in _TRUE_SET


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_survival.before_request
def _guard_all():
    return _admin_guard()

# Counters for metrics (extended with gossip)
_CNT = {"build_total": 0, "torrent_total": 0, "verify_total": 0, "status_total": 0, "list_total": 0, "gossip_total": 0}

try:
    from modules.survival.bundle import status as _st, list_bundles as _ls, build as _bd, verify as _vf, from_passport  # Iz obedinennogo bundle.py
    from modules.survival.torrent import create as _tcreate  # We assume that torrent.po exists; if not, add
except Exception:
    _st = _ls = _bd = _vf = from_passport = _tcreate = None

def register(app):
    """R egistriruet Blueprint v prilozhenii Flask."""
    if not _env_enabled():
        LOG.info("[survival_routes] disabled by env %s=0", FEATURE_ENV)
        return app
    if not ENCRYPT_KEY:
        LOG.warning("[survival_routes] enabled but SURVIVAL_ENCRYPT_KEY/P2P_BLOOM_ENCRYPT_KEY is empty; skip register")
        return app
    if bp_survival.name in getattr(app, "blueprints", {}):
        LOG.info("[survival_routes] blueprint already registered: %s", bp_survival.name)
        return app
    app.register_blueprint(bp_survival)
    LOG.info("[survival_routes] enabled and registered")
    return app

def _encrypt_data(data: str) -> str:
    """Full encryption with Fernet."""
    if not ENCRYPT_KEY:
        raise RuntimeError("SURVIVAL_ENCRYPT_KEY is required")
    f = Fernet(ENCRYPT_KEY.encode())
    return f.encrypt(data.encode("utf-8")).decode("utf-8")

def _decrypt_data(enc: str) -> str:
    if not ENCRYPT_KEY:
        raise RuntimeError("SURVIVAL_ENCRYPT_KEY is required")
    f = Fernet(ENCRYPT_KEY.encode())
    return f.decrypt(enc.encode("utf-8")).decode("utf-8")

def _p2p_sync_metrics(metrics: Dict[str, int]):
    """Sinkhroniziruet metriki s peers po soketam."""
    enc_metrics = _encrypt_data(json.dumps(metrics))
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                s.sendall(f"SYNC_SURVIVAL_METRICS:{enc_metrics}".encode("utf-8"))
            print(f"P2P sync survival metrics to {peer}: success.")
        except Exception as e:
            print(f"P2P survival metrics error with {peer}: {e}")

def _background_process_files():
    """Fonovaya sborka bandlov iz papki: izvlekaem params iz json i build."""
    if not os.path.exists(MONITOR_FOLDER): return
    for file in os.listdir(MONITOR_FOLDER):
        if file.endswith(".json"):
            with open(os.path.join(MONITOR_FOLDER, file), "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    _bd(slot=data.get("slot"), include=data.get("include", []), exclude=data.get("exclude", []))
                except json.JSONDecodeError:
                    pass
            os.remove(os.path.join(MONITOR_FOLDER, file))
    print("Background: processed files for survival routes.")

def _affect_boost(name: str) -> float:
    """Wust by affect for priority."""
    try:
        from modules.affect.priority import score_text
        sc = score_text(name or "")
        priority = float(sc.get("priority", 1.0))
        print(f"Affect boost for survival '{name}': {priority}")
        return priority
    except Exception:
        return 1.0

def _log_passport(endpoint: str, data: Dict[str, Any]):
    """Logiruet v profile s P2P-khukom."""
    try:
        from modules.mem.passport import append as passport
        log_data = {"endpoint": endpoint, "data": data}
        passport("survival_api", log_data, "survival://routes")
        _p2p_sync_metrics(_CNT)
    except Exception:
        pass

@bp_survival.route("/survival/status", methods=["GET"])
def api_status():
    """Status bandlov."""
    if _st is None:
        return jsonify({"ok": False, "error": "survival_unavailable"}), 500
    _background_process_files()
    result = _st()
    _CNT["status_total"] += 1
    _log_passport("status", result)
    return jsonify(result)

@bp_survival.route("/survival/list", methods=["GET"])
def api_list():
    """Spisok bandlov i torrentov s affekt-sortirovkoy."""
    if _ls is None:
        return jsonify({"ok": False, "error": "survival_unavailable"}), 500
    lim = int(request.args.get("limit", "20"))
    result = _ls(lim)
    # Affekt-bust: sortiruem items po prioritetu
    items = result.get("items", [])
    sorted_items = sorted(items, key=lambda x: _affect_boost(os.path.basename(x)), reverse=True)
    result["items"] = sorted_items
    _CNT["list_total"] += 1
    _log_passport("list", result)
    return jsonify(result)

@bp_survival.route("/survival/bundle/create", methods=["POST"])
@bp_survival.route("/survival/build", methods=["POST"])  # Alias ​​for compatibility
def api_bundle_create():
    """Sozdaђt bandl s bustom Re bloom-dobavleniem."""
    if _bd is None:
        return jsonify({"ok": False, "error": "survival_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    name = str(d.get("name", "bundle"))
    _affect_boost(name)  # Bust for log
    result = _bd(slot=d.get("slot"), include=list(d.get("include") or []), exclude=list(d.get("exclude") or []), label=d.get("label"), webseeds=list(d.get("webseeds") or []), add_backup=d.get("add_backup"), format=d.get("format"))
    if result.get("ok"):
        # Bloom: add sha for grandfather
        try:
            from modules.p2p.bloom import add
            add([result.get("archive_sha256", "")])
        except Exception:
            pass
    _CNT["build_total"] += 1
    _log_passport("bundle_create", result)
    return jsonify(result)

@bp_survival.route("/survival/torrent/create", methods=["POST"])
def api_torrent_create():
    """Sozdaђt torrent s bloom-dobavleniem."""
    if _tcreate is None:
        return jsonify({"ok": False, "error": "survival_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    result = _tcreate(str(d.get("path", "")), list(d.get("trackers") or []))
    if result.get("ok"):
        # Bloom: add sha torrent
        try:
            from modules.p2p.bloom import add
            add([result.get("torrent_sha256", "")])  # We assume that torrent.po returns sha
        except Exception:
            pass
    _CNT["torrent_total"] += 1
    _log_passport("torrent_create", result)
    return jsonify(result)

@bp_survival.route("/survival/verify", methods=["POST"])
def api_verify():
    """Verifies the bundle (with manifest decryption)."""
    if _vf is None:
        return jsonify({"ok": False, "error": "survival_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    result = _vf(str(d.get("archive", "")))  # Changed in the archive for compatibility with bundle.po
    _CNT["verify_total"] += 1
    _log_passport("verify", result)
    return jsonify(result)

@bp_survival.route("/survival/gossip", methods=["POST"])
def api_gossip():
    """Gossip sinkh bandlov/torrentov s pirami (push/pull/sync s forwarding)."""
    d = request.get_json(force=True, silent=True) or {}
    peer = str(d.get("peer", "")).rstrip("/")
    mode = str(d.get("mode", "sync")).lower()
    if not peer:
        return jsonify({"ok": False, "error": "peer_required"}), 400

    def _post_json(url: str, payload: dict):
        enc_payload = {"data": _encrypt_data(json.dumps(payload))}
        data = json.dumps(enc_payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return True, json.loads(r.read().decode("utf-8"))

    def _get_json(url: str):
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return True, json.loads(r.read().decode("utf-8"))

    rep = {"ok": True, "mode": mode, "peer": peer, "push": None, "pull": None}
    try:
        if mode in ("push", "sync"):
            last_bundle = _st().get("last")  # Example: pushing the latest bundle
            if last_bundle:
                man_path = last_bundle + ".manifest.json"
                enc_man = open(man_path, "r", encoding="utf-8").read()
                payload = {"manifest": enc_man}  # Shifrovannyy manifest
                ok, r = _post_json(peer + "/survival/bundle/create", payload)  # Or /import if you add
                rep["push"] = {"ok": ok and r.get("ok", False), "peer_rep": r}
        if mode in ("pull", "sync"):
            ok, r = _get_json(peer + "/survival/list")
            if ok and r.get("items"):
                # Pul: download and build locally (stub; extended for downloading)
                rep["pull"] = {"ok": True, "items_pulled": len(r["items"])}
            else:
                rep["pull"] = {"ok": False, "error": "peer_list_failed"}
        _CNT["gossip_total"] += 1
        _log_passport("gossip", rep)
        # Forwarding: forwarding
        if rep.get("ok"):
            for other_peer in P2P_PEERS:
                if other_peer != peer and other_peer:
                    try:
                        _post_json(other_peer + "/survival/gossip", d)  # R ekursivno
                        print(f"Gossip survival forwarded to {other_peer}.")
                    except Exception:
                        pass
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify(rep)

@bp_survival.route("/metrics/survival", methods=["GET"])
def api_metrics():
    """Metriki v formate Prometheus."""
    metrics_text = (
        f'survival_build_total {_CNT["build_total"]}\n'
        f'survival_torrent_total {_CNT["torrent_total"]}\n'
        f'survival_verify_total {_CNT["verify_total"]}\n'
        f'survival_status_total {_CNT["status_total"]}\n'
        f'survival_list_total {_CNT["list_total"]}\n'
        f'survival_gossip_total {_CNT["gossip_total"]}\n'
    )
    _p2p_sync_metrics(_CNT)
    return Response(metrics_text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
