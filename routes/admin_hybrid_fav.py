# -*- coding: utf-8 -*-
"""
routes/admin_hybrid_fav.py - upravlenie «izbrannymi tselyami» v adminke.

Marshruty:
  • GET  /admin/hybrid/favorites            - HTML
  • GET  /admin/hybrid/favorites/status     - tekuschee favorites.json
  • POST /admin/hybrid/favorites/add        - {targets:{lan?:{node}, tg?:{chat_id}}, reason?}
  • POST /admin/hybrid/favorites/remove     - {lan_node?|tg_chat?}
  • POST /admin/hybrid/favorites/enqueue    - {type,args,target:"lan"|"tg", id:<node|chat>}

Mosty:
- Yavnyy (UX ↔ Planirovanie): bystryy dostup k «lyubimym» mestam dostavki.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): vse cherez JSON-otvety, legko avtomatizirovat.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ne menyaet kontrakty ocheredi, tolko obertka nad enqueue().

Zemnoy abzats:
Pult s knopkami «na lyubimyy stanok» i «v nash obschiy chat» - menshe klikov i oshibok.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, render_template, request

from modules.hybrid.favorites import list_favorites, add_favorite, save_favorites, load_favorites  # type: ignore
from modules.hybrid.dispatcher import enqueue  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_fav = Blueprint("admin_hybrid_fav", __name__)

@bp_fav.get("/admin/hybrid/favorites")
def page():
    return render_template("admin_hybrid_fav.html")

@bp_fav.get("/admin/hybrid/favorites/status")
def status():
    return jsonify(list_favorites())

@bp_fav.post("/admin/hybrid/favorites/add")
def api_add():
    body = request.get_json(silent=True) or {}
    targets = body.get("targets") or {}
    reason = (body.get("reason") or "").strip()
    return jsonify(add_favorite(targets, reason=reason))

@bp_fav.post("/admin/hybrid/favorites/remove")
def api_remove():
    body = request.get_json(silent=True) or {}
    lan = (body.get("lan_node") or "").strip()
    tg  = body.get("tg_chat")
    obj = load_favorites()
    if lan:
        obj["lan_nodes"] = [x for x in (obj.get("lan_nodes") or []) if x != lan]
    if tg is not None:
        try: tg = int(tg)
        except Exception: pass
        obj["tg_chats"] = [x for x in (obj.get("tg_chats") or []) if x != tg]
    return jsonify(save_favorites(obj))

@bp_fav.post("/admin/hybrid/favorites/enqueue")
def api_enqueue():
    body = request.get_json(silent=True) or {}
    jtype = (body.get("type") or "").strip()
    args  = body.get("args") or {}
    target_kind = (body.get("target") or "").strip().lower()
    ident = body.get("id")
    if not jtype or not target_kind or ident in (None, ""):
        return jsonify({"ok": False, "error": "bad-request"}), 400
    targets = {}
    if target_kind == "lan":
        targets={"lan":{"node": str(ident)}}
    elif target_kind == "tg":
        try: ident = int(ident)
        except Exception: pass
        targets={"tg":{"chat_id": ident}}
    else:
        return jsonify({"ok": False, "error": "unknown-target"}), 400
    return jsonify(enqueue(jtype, args, targets, policy="lan_then_tg"))

def register_admin_hybrid_fav(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_fav)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_hybrid_fav_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/hybrid/favorites")
        def _p(): return page()

        @pref.get("/admin/hybrid/favorites/status")
        def _s(): return status()

        @pref.post("/admin/hybrid/favorites/add")
        def _a(): return api_add()

        @pref.post("/admin/hybrid/favorites/remove")
        def _r(): return api_remove()

        @pref.post("/admin/hybrid/favorites/enqueue")
        def _e(): return api_enqueue()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_fav)
    return app