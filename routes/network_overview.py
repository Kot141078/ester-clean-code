# -*- coding: utf-8 -*-
"""routes/network_overview.py - UI/REST: svodnaya “Set uzlov” (sosedi + info-kesh + bystrye deystviya).

Route:
  • GET /admin/network - HTML
  • GET /admin/network/status - {peers, info_cache, local_tasks}
  • POST /admin/network/hello - razoslat hello seychas (LAN_GROUP:LAN_PORT)
  • POST /admin/network/info-request - zaprosit info u vsekh or u konkretnogo IP
  • POST /admin/network/task-ping - postavit zadachu ping na IP (or broadcast)
  • POST /admin/network/clear-cache - ochistit info-cash

Mosty:
- Yavnyy (Nablyudaemost ↔ Orkestratsiya): odin ekran vidit sosedey i sostoyanie vorkerov (read-only).
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): HMAC dlya info/hello, AB-rezhim otrazhen; kesh khranitsya lokalno.
- Skrytyy 2 (Praktika ↔ Sovmestimost): formaty sovpadayut s uzhe suschestvuyuschimi LAN/LAN-tasks.

Zemnoy abzats:
Eto “schitok dispetchera”: kto vokrug, kto rabotaet, skolko zadach - i para knopok “pozvat” i “verit”.

# c=a+b"""
from __future__ import annotations

import json, os, socket, time
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.lan.lan_settings import load_settings  # group/key/port
from modules.lan.lan_crypto import sign
from modules.lan.lan_tasks import _load_db as _load_tasks_db, new_task, enqueue_outbox
from modules.lan.lan_tasks_settings import load_tasks_settings
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_net = Blueprint("network_overview", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
PEERS = STATE_DIR / "lan_peers.json"
INFOC = STATE_DIR / "lan_info_cache.json"

def _load_json(p: Path):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _send_json(j: dict, addr: tuple[str,int], key: str):
    raw = json.dumps(j, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    pkt = dict(j); pkt["sig"] = sign(raw, key) if key else ""
    data = json.dumps(pkt, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    s.sendto(data, addr)
    s.close()

@bp_net.get("/admin/network")
def page():
    return render_template("network_overview.html", ab=AB)

@bp_net.get("/admin/network/status")
def api_status():
    peers = _load_json(PEERS)
    info = _load_json(INFOC)
    cfg = load_settings()
    tcfg = load_tasks_settings()
    db = _load_tasks_db()
    counts = {k: len((db.get(k) or {})) for k in ("outbox","inbox","active","done")}
    return jsonify({
        "ok": True, "ab": AB,
        "lan": {"enabled": bool(cfg.get("enable")), "group": cfg.get("group"), "port": cfg.get("port"), "key_set": bool(cfg.get("shared_key"))},
        "tasks": {"cfg": {"enable": tcfg.get("enable"), "max_active": tcfg.get("max_active"), "accept": tcfg.get("accept")}, "counts": counts},
        "peers": peers, "info_cache": info
    })

@bp_net.post("/admin/network/hello")
def api_hello():
    s = load_settings()
    if not s.get("enable"):
        return jsonify({"ok": False, "error": "lan-disabled"}), 400
    try:
        import platform
        nid = platform.node()
    except Exception:
        nid = "node"
    hello = {"t":"hello","ts":int(time.time()),"node":{"id":nid,"name":nid},"port": s["port"],"payload":{"ab":AB,"v":1}}
    _send_json(hello, (s["group"], int(s["port"])), s.get("shared_key",""))
    return jsonify({"ok": True})

@bp_net.post("/admin/network/info-request")
def api_info():
    s = load_settings()
    if not s.get("enable"):
        return jsonify({"ok": False, "error": "lan-disabled"}), 400
    body = request.get_json(silent=True) or {}
    ip = (body.get("ip") or "").strip()
    j = {"t":"info.req","ts":int(time.time()),"node":{"id":_node_id(),"name":_node_id()},"payload":{}}
    port = int(os.getenv("LAN_INFO_PORT","54547"))
    if ip:
        _send_json(j, (ip, port), s.get("shared_key",""))
    else:
        _send_json(j, (s.get("group","239.255.43.21"), port), s.get("shared_key",""))
    return jsonify({"ok": True})

@bp_net.post("/admin/network/task-ping")
def api_task_ping():
    body = request.get_json(silent=True) or {}
    ip = (body.get("ip") or "").strip()
    pr = int(body.get("priority") or 5)
    t = new_task("ping", {}, priority=pr, to_ip=ip)
    enqueue_outbox(t)
    return jsonify({"ok": True, "task": {"id": t["id"], "type": "ping", "priority": pr, "to_ip": ip}})

@bp_net.post("/admin/network/clear-cache")
def api_clear_cache():
    try:
        INFOC.write_text(json.dumps({"peers": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return jsonify({"ok": True})

def _node_id():
    try:
        import platform
        return platform.node()
    except Exception:
        return "node"

def register_network_overview(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_net)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("network_overview_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/network")
        def _p(): return page()

        @pref.get("/admin/network/status")
        def _s(): return api_status()

        @pref.post("/admin/network/hello")
        def _h(): return api_hello()

        @pref.post("/admin/network/info-request")
        def _i(): return api_info()

        @pref.post("/admin/network/task-ping")
        def _tp(): return api_task_ping()

        @pref.post("/admin/network/clear-cache")
        def _c(): return api_clear_cache()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_net)
    return app