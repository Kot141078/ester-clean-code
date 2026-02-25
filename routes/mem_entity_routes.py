# -*- coding: utf-8 -*-
"""routes/mem_entity_routes.py - REST: izvlechenie i privyazka suschnostey k pamyati/grafu (paketnyy + tekstovyy rezhim).
(sovmestimaya s dampom versiya s uluchsheniyami dlya “Ester”).

Mosty:
- Yavnyy: (Veb ↔ KG) bystraya razmetka teksta i linkovka uzlov v graf pamyati (paketnyy i tekstovyy).
- Skrytyy #1: (Profile ↔ Audit) modul pishet sobytiya v “profile”.
- Skrytyy #2: (P2P ↔ Memory) optsionalnaya rassylka sobytiy na piry (UDP-pleyskholder).

Zemnoy abzats:
Podali tekst - poluchili spisok imen/terminov i ID uzlov; paketnaya obrabotka uskoryaet rabotu.
Optionalno sobytiya ukhodyat sosedyam v seti dlya legkoy konsistentnosti.

c=a+b"""
from __future__ import annotations

import os
import json
import base64
import socket
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Konstanty
P2P_PEERS = [p.strip() for p in (os.getenv("ESTER_P2P_PEERS") or "").split(",") if p.strip()]  # ip:port
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # folder for background collection .txt
SECRET = os.getenv("ESTER_ENTITY_SECRET", "ester-entity-secret")  # for future encryption (optional)

bp = Blueprint("mem_entity", __name__)

# Soft kernel import
try:
    from modules.mem.entity_linker import link_entities as _link, shadow_status as _status  # type: ignore
except Exception:  # pragma: no cover
    _link = None  # type: ignore
    _status = None  # type: ignore


def _encrypt_response(result: Dict[str, Any]) -> str:
    """“Encryption” placeholder: bassier64(ZhSON)."""
    return base64.b64encode(json.dumps(result, ensure_ascii=False).encode("utf-8")).decode("utf-8")


def _p2p_sync(event: str, payload: Dict[str, Any]) -> None:
    """Otpravka UDP-notifikatsii pirami (best-effort)."""
    if not P2P_PEERS:
        return
    try:
        msg = _encrypt_response({"event": event, "data": payload})
    except Exception:
        return
    for peer in P2P_PEERS:
        try:
            host, port_s = peer.split(":")
            port = int(port_s)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.sendto(msg.encode("utf-8"), (host, port))
            s.close()
        except Exception:
            pass  # never drops worker thread


def _background_collect_texts() -> List[Dict[str, str]]:
    """Returns new *.txt from MONITOR_FOLDER and deletes them (without calling _link)."""
    if not os.path.isdir(MONITOR_FOLDER):
        return []
    out: List[Dict[str, str]] = []
    for fn in os.listdir(MONITOR_FOLDER):
        if not fn.endswith(".txt"):
            continue
        path = os.path.join(MONITOR_FOLDER, fn)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            out.append({"id": f"bg::{fn}", "text": text})
        except Exception:
            continue
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
    if out:
        _p2p_sync("bg_texts_collected", {"n": len(out)})
    return out


def _affect_boost(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Boost entities by affect (this is anchor). Safe to the absence of a value field."""
    try:
        from modules.affect.priority import score_text  # type: ignore
        for e in entities:
            val = str(e.get("value", "") or "")
            try:
                sc = score_text(val) or {}
                e["boost"] = float(sc.get("priority", 1.0))
            except Exception:
                e["boost"] = 1.0
        return entities
    except Exception:
        return entities


def _log_passport(endpoint: str, data: Dict[str, Any]) -> None:
    """Log in memory “profile” (if available) + easy P2P event synchronization."""
    try:
        from modules.mem.passport import append as passport  # type: ignore
        passport("mem_entity_api", {"endpoint": endpoint, "data": data}, "mem://entity/api")
    except Exception:
        pass
    _p2p_sync(endpoint, data)


@bp.route("/mem/entity/link", methods=["POST"])
def api_link():
    if _link is None:
        return jsonify({"ok": False, "error": "entity_unavailable"}), 500

    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    # Supports both modes: batch and text
    items: List[Dict[str, Any]] = list(d.get("items") or [])
    if not items and "text" in d:
        items = [{"id": "api_text", "text": str(d.get("text") or "")}]

    if not items:
        return jsonify({"ok": False, "error": "items or text required"}), 400

    if bool(d.get("attach_background", True)):
        items.extend(_background_collect_texts())

    try:
        rep = _link(items)  # type: ignore[misc]
    except Exception as e:
        _log_passport("link_fail", {"n": len(items), "error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500

    # Unification of the answer
    if isinstance(rep, dict):
        entities = list(rep.get("entities") or [])
        rep["entities"] = _affect_boost(entities)
        out = {"ok": bool(rep.get("ok", True)), **rep}
    else:
        boosted = _affect_boost(list(rep or []))  # type: ignore[arg-type]
        out = {"ok": True, "entities": boosted}

    _log_passport("link", {"n": len(items), "entities": len(out.get("entities", []))})

    if d.get("encrypted"):
        return jsonify({"ok": True, "encrypted": _encrypt_response(out)})

    return jsonify(out)


@bp.route("/mem/entity/status", methods=["GET"])
def api_status():
    if _status is None:
        return jsonify({"ok": False, "error": "entity_unavailable"}), 500
    try:
        rep = _status()  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    rep = dict(rep or {})
    rep["metrics"] = {
        "runs": rep.get("runs", 0),
        "linked": rep.get("linked", 0),
    }
    return jsonify({"ok": True, **rep})


def register_routes(app, seen_endpoints=None):
    """Registration of blueprint and aliases."""
    app.register_blueprint(bp)
    app.add_url_rule("/memory/entity/link", view_func=api_link, methods=["POST"])
    app.add_url_rule("/memory/entity/status", view_func=api_status, methods=["GET"])


# Unified project hooks
def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    app.register_blueprint(bp)


__all__ = ["bp", "register_routes", "register", "init_app"]
# c=a+b