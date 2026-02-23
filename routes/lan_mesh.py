# -*- coding: utf-8 -*-
"""
routes/lan_mesh.py - UI/REST dlya LAN-obnaruzheniya i obmena «profileami».

Marshruty:
  • GET  /admin/lan              - HTML
  • GET  /admin/lan/status       - {settings, env, peers}
  • POST /admin/lan/save         - sokhranit nastroyki
  • POST /admin/lan/ping         - razoslat hello seychas
  • POST /admin/lan/request      - zaprosit «profile» u vsekh ili u ip
  • POST /admin/lan/peers/clear  - ochistit kesh sosedey

Mosty:
- Yavnyy (Kibernetika ↔ Nablyudaemost): karta sosedey i bystrye deystviya.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): obschiy klyuch i flag verified v spiske sosedey.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ne trogaem mozg/pamyat/volyu - tolko infrastruktura.

Zemnoy abzats:
Odin ekran: vklyuchil LAN, uvidel sosedey, pri neobkhodimosti «pozval profilea» - bez lishney rutiny.

# c=a+b
"""
from __future__ import annotations

import json, os, socket
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.lan.lan_settings import load_settings, save_settings  # type: ignore
from modules.lan.lan_crypto import sign  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lan = Blueprint("lan_mesh", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
PEERS = STATE_DIR / "lan_peers.json"

def _load_peers():
    try:
        if PEERS.exists():
            return json.loads(PEERS.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"peers": {}}

def _save_peers(d):
    try:
        PEERS.parent.mkdir(parents=True, exist_ok=True)
        PEERS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _send_json(j: dict, addr: tuple[str,int], key: str):
    raw = json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    pkt = dict(j); pkt["sig"] = sign(raw, key) if key else ""
    data = json.dumps(pkt, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    s.sendto(data, addr)
    s.close()

@bp_lan.get("/admin/lan")
def page():
    return render_template("lan_mesh.html", ab=AB)

@bp_lan.get("/admin/lan/status")
def api_status():
    s = load_settings()
    env = {
        "LAN_ENABLE": os.getenv("LAN_ENABLE",""),
        "LAN_GROUP": os.getenv("LAN_GROUP",""),
        "LAN_PORT": os.getenv("LAN_PORT",""),
        "LAN_INTERVAL": os.getenv("LAN_INTERVAL",""),
        "LAN_SHARED_KEY": "***" if (os.getenv("LAN_SHARED_KEY") or s.get("shared_key")) else "",
        "LAN_AUTO_EXCHANGE": os.getenv("LAN_AUTO_EXCHANGE",""),
        "LAN_MAX_PACKET": os.getenv("LAN_MAX_PACKET",""),
    }
    return jsonify({"ok": True, "ab": AB, "settings": s, "peers": _load_peers(), "env": env})

@bp_lan.post("/admin/lan/save")
def api_save():
    data = request.get_json(silent=True) or {}
    s = save_settings({
        "enable": bool(data.get("enable")),
        "group": str(data.get("group") or "239.255.43.21"),
        "port": int(data.get("port") or 54545),
        "interval": int(data.get("interval") or 15),
        "shared_key": str(data.get("shared_key") or ""),
        "auto_exchange": bool(data.get("auto_exchange", True)),
        "max_packet": int(data.get("max_packet") or 1400),
    })
    return jsonify({"ok": True, "settings": s})

@bp_lan.post("/admin/lan/ping")
def api_ping():
    s = load_settings()
    if not s.get("enable"):
        return jsonify({"ok": False, "error": "lan-disabled"}), 400
    try:
        import platform
        nid = platform.node()
    except Exception:
        nid = "node"
    hello = {"t":"hello","ts":int(__import__("time").time()),"node":{"id":nid,"name":nid},"port": s["port"],"payload":{"ab":AB,"v":1}}
    _send_json(hello, (s["group"], int(s["port"])), s.get("shared_key",""))
    return jsonify({"ok": True})

@bp_lan.post("/admin/lan/request")
def api_request():
    s = load_settings()
    if not s.get("enable"):
        return jsonify({"ok": False, "error": "lan-disabled"}), 400
    body = request.get_json(silent=True) or {}
    ip = (body.get("ip") or "").strip()
    j = {"t":"req","ts":int(__import__("time").time()),"node":{"id":_node_id(),"name":_node_id()},"port": s["port"],"payload":{}}
    if ip:
        _send_json(j, (ip, int(s["port"])), s.get("shared_key",""))
    else:
        _send_json(j, (s["group"], int(s["port"])), s.get("shared_key",""))
    return jsonify({"ok": True})

@bp_lan.post("/admin/lan/peers/clear")
def api_clear():
    _save_peers({"peers": {}})
    return jsonify({"ok": True})

def _node_id():
    try:
        import platform
        return platform.node()
    except Exception:
        return "node"

def register_lan_mesh(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lan)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_mesh_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lan")
        def _p(): return page()

        @pref.get("/admin/lan/status")
        def _s(): return api_status()

        @pref.post("/admin/lan/save")
        def _sv(): return api_save()

        @pref.post("/admin/lan/ping")
        def _pg(): return api_ping()

        @pref.post("/admin/lan/request")
        def _rq(): return api_request()

        @pref.post("/admin/lan/peers/clear")
        def _cl(): return api_clear()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lan)
    return app