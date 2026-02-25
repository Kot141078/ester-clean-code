# -*- coding: utf-8 -*-
"""routes/p2p_bloom_routes.py - obedinennyy HTTP-servis dlya P2P deduplikatsii s Bloom-filtrom, gossip Re uluchsheniyami dlya Ester.

Predostavlyaet REST API, metriki i gossip dlya upravleniya raspredelennym Bloom-filtrom,
pozvolyaya uzlam effektivno obmenivatsya informatsiey o vidennykh identifikatorakh.

Endpointy (expansive s sovmestimostyu):
  • GET /p2p/bloom/state | /p2p/bloom/status v†' {"bits":..., "k":..., "added":...} (alias)
  • GET /p2p/bloom/export.bin | /p2p/bloom/export v†' (raw binary or json blob)
  • POST /p2p/bloom/announce | /p2p/bloom/add {"ids":[...]} v†' {"added": N} (alias)
  • POST /p2p/bloom/check {"ids":[...]} v†' {"present":[...], "absent":[...], "seen":[...], "new":[...]} (expanded)
  • POST /p2p/bloom/merge (raw binary | json base64) v†' {"ok": true}
  • POST /p2p/bloom/import (blob) v†' {"ok": true} (alias dlya merge)
  • POST /p2p/bloom/reset v†' {"ok": true}
  • POST /p2p/bloom/gossip {"peer":..., "mode":...} v†' {"ok": true, "push/pull":...} (gossip s push/pull/sync)
  • GET /metrics/p2p_bloom v†' (prometheus text format s stats, vklyuchaya gossip)

Mosty:
- Yavnyy: (Set v†" Memory) Ekonomiya trafika za schet obmena kompaktnymi strukturami dannykh.
- Skrytyy #1: (Infoteoriya v†" Masshtab) Bneshnie filtry obedinyayutsya bez zhestkikh trebovaniy k parametram.
- Skrytyy #2: (Kibernetika v†" Nadezhnost) Prostye interfeysy Re metriki dlya kontrolya Re otkazoustoychivosti.
- Skrytyy #3: (Profile v†" Trassirovka) operatsii vidny s P2P-khukom.
- Skrytyy #4: (Rules/Watch v†" Avtonomiya) legko zvat iz pravil/skanera.
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) realnyy P2P-obmen metrikami cherez socket Re gossip po HTTP.
- Uluchshenie: (Avtonomiya v†" VZ) fonovaya obrabotka ID iz zaprosov/papok/gossip, addavlenie v VZ.
- Uluchshenie: (Affekt v†" Prioritet) bust "tђplykh" ID v announce/check (vliyaet na prioritet v VZ).
- Uluchshenie: (Bezopasnost v†" Prozrachnost) polnotsennoe shifrovanie s Fernet dlya obmena v gossip/merge.
- Iz py1: gossip s push/pull/sync cherez urllib, s forwarding dlya tsepochki.

Zemnoy abzats:
Eto setevoe “sito” dlya ID: v nego mozhno dobavlyat elementy, proveryat nalichie, delitsya ego sostoyaniem s drugimi Re sledit za ego rabotoy. Glya Ester - eto kak vospominaniya: raspredelennye, teplye Re s dushoy, where dubli filtruyutsya kollektivno po seti agentov, s gossip dlya "spleten" o novykh ID.

# c=a+b (teper s nastoyaschim gossip)"""
from __future__ import annotations
from flask import Blueprint, Response, jsonify, request
import logging
import os
import json
import base64
import gzip  # Looking at compression in export
import urllib.request
import urllib.error
import socket
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
from modules.security.admin_guard import require_admin

# Encryption look (same as bloom.po)
try:
    from cryptography.fernet import Fernet
except ImportError:
    raise ImportError("Install cryptography: pip install cryptography")

LOG = logging.getLogger("routes.p2p_bloom_routes")
FEATURE_ENV = "ESTER_P2P_BLOOM_ENABLED"
_TRUE_SET = {"1", "true", "yes", "on", "y"}

# Constants for Esther
DB = os.getenv("P2P_BLOOM_DB", "data/p2p/bloom.json")  # Glya sovmestimosti
P2P_PEERS = [p.strip() for p in str(os.getenv("ESTER_P2P_PEERS", "") or "").split(",") if p.strip()]
FALLBACK_DOCS_PATH = os.getenv("HYBRID_FALLBACK_DOCS", "data/mem/docs.jsonl")  # Glya fonovoy v VZ
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # Background folder
ENCRYPT_KEY = str(os.getenv("P2P_BLOOM_ENCRYPT_KEY", "") or "").strip()
TIMEOUT = int(os.getenv("P2P_GOSSIP_TIMEOUT", "8"))  # Iz py1

bp_p2p_bloom = Blueprint("p2p_bloom", __name__)


def _env_enabled() -> bool:
    return str(os.getenv(FEATURE_ENV, "0") or "0").strip().lower() in _TRUE_SET


def _admin_guard():
    ok, reason = require_admin(request)
    if ok:
        return None
    return jsonify({"ok": False, "error": "forbidden", "reason": reason}), 403


@bp_p2p_bloom.before_request
def _guard_all():
    return _admin_guard()

# Counters for metrics (extended with gossip)
_CNT = {"announce_total": 0, "check_total": 0, "merge_total": 0, "status_total": 0, "gossip_total": 0, "import_total": 0, "reset_total": 0}

try:
    from modules.p2p.bloom import status as _st, add as _add, check as _check, merge as _merge, reset as _reset, export_blob as _exp, import_blob as _imp  # Iz obedinennogo bloom.py
except Exception:
    _st = _add = _check = _merge = _reset = _exp = _imp = None

def register(app):
    """R egistriruet Blueprint v prilozhenii Flask."""
    if not _env_enabled():
        LOG.info("[p2p_bloom_routes] disabled by env %s=0", FEATURE_ENV)
        return app
    if not ENCRYPT_KEY:
        LOG.warning("[p2p_bloom_routes] enabled but P2P_BLOOM_ENCRYPT_KEY is empty; skip register")
        return app
    if bp_p2p_bloom.name in getattr(app, "blueprints", {}):
        LOG.info("[p2p_bloom_routes] blueprint already registered: %s", bp_p2p_bloom.name)
        return app
    app.register_blueprint(bp_p2p_bloom)
    LOG.info("[p2p_bloom_routes] enabled and registered")
    return app

def _encrypt_data(data: str) -> str:
    """Full encryption with Fernet."""
    if not ENCRYPT_KEY:
        raise RuntimeError("P2P_BLOOM_ENCRYPT_KEY is required")
    f = Fernet(ENCRYPT_KEY.encode())
    return f.encrypt(data.encode("utf-8")).decode("utf-8")

def _decrypt_data(enc: str) -> str:
    if not ENCRYPT_KEY:
        raise RuntimeError("P2P_BLOOM_ENCRYPT_KEY is required")
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
                s.sendall(f"SYNC_BLOOM_METRICS:{enc_metrics}".encode("utf-8"))
            print(f"P2P sync metrics to {peer}: success.")
        except Exception as e:
            print(f"P2P metrics error with {peer}: {e}")

def _background_process_ids(ids: List[str]):
    """Background ID processing: add it to the ID as a dox, with priority by bust."""
    if not ids: return
    for i, id_str in enumerate(ids):
        boost = _affect_boost(id_str)
        if boost > 0.5:  # Tolko "tђplye" v VZ
            new_doc = {"id": f"bloom_api_{i}", "text": id_str, "priority": boost}
            with open(FALLBACK_DOCS_PATH, "a", encoding="utf-8") as out:
                out.write(json.dumps(new_doc) + "\n")
    print("Background: added priority IDs to BZ from bloom API.")

def _background_process_files():
    """Background processing of files from a folder: extract ID."""
    if not os.path.exists(MONITOR_FOLDER): return []
    new_ids = []
    for file in os.listdir(MONITOR_FOLDER):
        if file.endswith(".json"):
            with open(os.path.join(MONITOR_FOLDER, file), "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    new_ids.extend(data.get("ids", []))
                except json.JSONDecodeError:
                    pass
            os.remove(os.path.join(MONITOR_FOLDER, file))
    _background_process_ids(new_ids)
    print("Background: processed files for bloom routes.")
    return new_ids

def _affect_boost(id_str: str) -> float:
    """Vust ID po affektu."""
    try:
        from modules.affect.priority import score_text
        sc = score_text(id_str or "")
        priority = float(sc.get("priority", 1.0))
        print(f"Affect boost for ID '{id_str}': {priority}")
        return priority
    except Exception:
        return 1.0

def _log_passport(endpoint: str, data: Dict[str, Any]):
    """Logiruet v profile s P2P-khukom."""
    try:
        from modules.mem.passport import append as passport
        log_data = {"endpoint": endpoint, "data": data}
        passport("p2p_bloom_api", log_data, "p2p://bloom/api")
        _p2p_sync_metrics(_CNT)
    except Exception:
        pass

@bp_p2p_bloom.route("/p2p/bloom/state", methods=["GET"])
@bp_p2p_bloom.route("/p2p/bloom/status", methods=["GET"])
def api_state():
    """Returns the current state of the filter."""
    if _st is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
    _background_process_files()
    result = _st()
    _CNT["status_total"] += 1
    _log_passport("state", result)
    return jsonify(result)

@bp_p2p_bloom.route("/p2p/bloom/export.bin", methods=["GET"])
@bp_p2p_bloom.route("/p2p/bloom/export", methods=["GET"])
def api_export():
    """Eksportiruet binarnoe ili json predstavlenie filtra (s shifrovaniem)."""
    if _exp is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
    blob = _exp()["blob"]
    if request.path.endswith(".bin"):
        # Binary: compress Re encrypt
        gz = gzip.compress(json.dumps(blob).encode("utf-8"))
        enc = _encrypt_data(base64.b64encode(gz).decode("ascii"))
        return Response(enc.encode("utf-8"), mimetype="application/octet-stream")
    else:
        return jsonify({"ok": True, "blob": blob})

@bp_p2p_bloom.route("/p2p/bloom/announce", methods=["POST"])
@bp_p2p_bloom.route("/p2p/bloom/add", methods=["POST"])
def api_announce():
    """Dobavlyaet ID v filtr s bustom."""
    if _add is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    ids = list(d.get("ids") or [])
    for id_str in ids:
        _affect_boost(id_str)
    _background_process_ids(ids)
    result = _add(ids)
    _CNT["announce_total"] += result.get("added", 0)
    _log_passport("announce", result)
    return jsonify({"ok": True, **result})

@bp_p2p_bloom.route("/p2p/bloom/check", methods=["POST"])
def api_check():
    """Checks for the presence of an ID in the filter."""
    if _check is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    ids = list(d.get("ids") or [])
    for id_str in ids:
        _affect_boost(id_str)
    _background_process_ids(ids)
    result = _check(ids)
    _CNT["check_total"] += len(ids)
    result["present"] = result.get("seen", [])
    result["absent"] = result.get("new", [])
    _log_passport("check", result)
    return jsonify({"ok": True, **result})

@bp_p2p_bloom.route("/p2p/bloom/merge", methods=["POST"])
@bp_p2p_bloom.route("/p2p/bloom/import", methods=["POST"])  # Alias ​​for compatibility
def api_merge():
    """Combines the current filter with an external one (with type processing and encryption)."""
    if _merge is None or _imp is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
    content_type = request.headers.get("Content-Type", "")
    try:
        if "application/octet-stream" in content_type or not content_type:
            blob = request.get_data(cache=False)
            if not blob:
                return jsonify({"ok": False, "error": "Empty request body"}), 400
            # Decryption Re decompression
            dec = _decrypt_data(blob.decode("utf-8"))
            gz = base64.b64decode(dec)
            data = json.loads(gzip.decompress(gz))
            meta = data.get("head", {})
            arr_in = data.get("data", [])
            report = _merge(meta.get("bits"), meta.get("k"), arr_in, meta.get("salt"))
            _CNT["merge_total"] += 1
            _log_passport("merge", report)
            return jsonify(report)
        elif "application/json" in content_type:
            d = request.get_json(force=True, silent=True) or {}
            enc_data = d.get("data") or ""
            if not enc_data:
                return jsonify({"ok": False, "error": "Missing 'data' field"}), 400
            dec_data = json.loads(_decrypt_data(enc_data))
            meta = d.get("meta") or {}
            report = _merge(meta.get("bits"), meta.get("k"), dec_data, meta.get("salt"))
            _CNT["merge_total"] += 1
            _log_passport("merge", report)
            return jsonify(report)
        else:
            return jsonify({"ok": False, "error": "Unsupported Content-Type"}), 415
    except Exception as e:
        return jsonify({"ok": False, "error": f"Merge failed: {e}"}), 500

@bp_p2p_bloom.route("/p2p/bloom/reset", methods=["POST"])
def api_reset():
    """Sbrasyvaet filtr."""
    if _reset is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
    result = _reset(force=True)
    _CNT["reset_total"] += 1
    _log_passport("reset", result)
    return jsonify(result)

@bp_p2p_bloom.route("/p2p/bloom/gossip", methods=["POST"])
def api_gossip():
    """Gossip s pirami: push/pull/sync s forwarding."""
    if _exp is None or _imp is None:
        return jsonify({"ok": False, "error": "bloom_unavailable"}), 500
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
            my_blob = _exp()["blob"]
            ok, r = _post_json(peer + "/p2p/bloom/import", my_blob)
            rep["push"] = {"ok": ok and r.get("ok", False), "peer_rep": r}
        if mode in ("pull", "sync"):
            ok, r = _get_json(peer + "/p2p/bloom/export")
            if ok and r.get("blob"):
                rep["pull"] = _imp(r["blob"])
            else:
                rep["pull"] = {"ok": False, "error": "peer_export_failed"}
        _CNT["gossip_total"] += 1
        _log_passport("gossip", rep)
        # Forwarding for gossip: sending the updated blob to other peers
        if rep.get("ok"):
            updated_blob = _exp()["blob"]
            for other_peer in P2P_PEERS:
                if other_peer != peer and other_peer:
                    try:
                        _post_json(other_peer + "/p2p/bloom/import", updated_blob)
                        print(f"Gossip forwarded to {other_peer}.")
                    except Exception:
                        pass
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify(rep)

@bp_p2p_bloom.route("/metrics/p2p_bloom", methods=["GET"])
def api_metrics():
    """Predostavlyaet metriki v formate Prometheus."""
    metrics_text = (
        f'p2p_bloom_announce_total {_CNT["announce_total"]}\n'
        f'p2p_bloom_check_total {_CNT["check_total"]}\n'
        f'p2p_bloom_merge_total {_CNT["merge_total"]}\n'
        f'p2p_bloom_status_total {_CNT["status_total"]}\n'
        f'p2p_bloom_gossip_total {_CNT["gossip_total"]}\n'
        f'p2p_bloom_import_total {_CNT["import_total"]}\n'
        f'p2p_bloom_reset_total {_CNT["reset_total"]}\n'
    )
    _p2p_sync_metrics(_CNT)
    return Response(metrics_text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
