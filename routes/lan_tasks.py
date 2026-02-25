# -*- coding: utf-8 -*-
"""routes/lan_tasks.py - UI/REST: raspredelennye zadachi po LAN.

Route:
  • GET /admin/lan/tasks - HTML
  • GET /admin/lan/tasks/status - sostoyanie ocheredi i nastroek
  • POST /admin/lan/tasks/submit - sozdat i otpravit zadachu
  • POST /admin/lan/tasks/clear - ochistit done
  • POST /admin/lan/tasks/settings - sokhranit nastroyki tasks (enable/port/interval/max_active/accept)

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): odin ekran dlya postanovki i nablyudeniya zadach v seti.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): viden AB-rezhim i HMAC obschim klyuchom (iz LAN).
- Skrytyy 2 (Praktika ↔ Sovmestimost): format zadach odin i tot zhe v UI/UDP/REST; drop-in.

Zemnoy abzats:
Zdes stavim “porucheniya sosedyam” i vidim, kak oni ispolnyayutsya - bez oblakov i lishnikh voprosov.

# c=a+b"""
from __future__ import annotations

import json
import os
from flask import Blueprint, jsonify, render_template, request

from modules.lan.lan_settings import load_settings as load_net  # key/group (read-only)
from modules.lan.lan_tasks_settings import load_tasks_settings, save_tasks_settings
from modules.lan.lan_tasks import new_task, enqueue_outbox, _load_db
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lantasks = Blueprint("lan_tasks", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_lantasks.get("/admin/lan/tasks")
def page():
    return render_template("lan_tasks.html", ab=AB)

@bp_lantasks.get("/admin/lan/tasks/status")
def api_status():
    net = load_net()
    cfg = load_tasks_settings()
    db = _load_db()
    # we will reduce the output of lists (only headers)
    def _short(d):
        arr=[]
        for k,v in (d or {}).items():
            t=(v.get("task") or v) if isinstance(v,dict) else v
            arr.append({"id": t.get("id",k), "type": (t.get("job") or {}).get("type"), "priority": t.get("priority"), "ts": t.get("ts")})
        return sorted(arr, key=lambda x: (-int(x.get("priority") or 0), int(x.get("ts") or 0)))[:50]
    return jsonify({
        "ok": True, "ab": AB,
        "net": {"group": net.get("group"), "key_set": bool(net.get("shared_key"))},
        "cfg": cfg,
        "counts": {k: len((db.get(k) or {})) for k in ("outbox","inbox","active","done")},
        "peek": {k: _short(db.get(k)) for k in ("outbox","inbox","active","done")}
    })

@bp_lantasks.post("/admin/lan/tasks/submit")
def api_submit():
    data = request.get_json(silent=True) or {}
    jtype = str(data.get("type") or "")
    params = data.get("params") or {}
    pr = int(data.get("priority") or 5)
    to_ip = str(data.get("to_ip") or "")
    t = new_task(jtype, params, priority=pr, to_ip=to_ip)
    enqueue_outbox(t)
    return jsonify({"ok": True, "task": {"id": t["id"], "type": jtype, "priority": pr, "to_ip": to_ip}})

@bp_lantasks.post("/admin/lan/tasks/clear")
def api_clear():
    from modules.lan.lan_tasks import _save_db
    d = _load_db(); d["done"] = {}; _save_db(d)
    return jsonify({"ok": True})

@bp_lantasks.post("/admin/lan/tasks/settings")
def api_settings():
    body = request.get_json(silent=True) or {}
    patch = {
        "enable": bool(body.get("enable")),
        "port": int(body.get("port", 54546)),
        "interval": max(3, int(body.get("interval", 10))),
        "max_active": max(1, int(body.get("max_active", 1))),
        "accept": body.get("accept") or ["ping","text.digest","llm.chat"],
    }
    s = save_tasks_settings(patch)
    return jsonify({"ok": True, "cfg": s})

def register_lan_tasks(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lantasks)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_tasks_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lan/tasks")
        def _p(): return page()

        @pref.get("/admin/lan/tasks/status")
        def _s(): return api_status()

        @pref.post("/admin/lan/tasks/submit")
        def _sub(): return api_submit()

        @pref.post("/admin/lan/tasks/clear")
        def _cl(): return api_clear()

        @pref.post("/admin/lan/tasks/settings")
        def _set(): return api_settings()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lantasks)
    return app