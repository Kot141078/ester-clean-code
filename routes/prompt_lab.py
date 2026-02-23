# -*- coding: utf-8 -*-
"""
routes/prompt_lab.py - UI/REST PromptLab: shablony, prevyu, zapusk setki, diff, vybor luchshego, eksport.

Marshruty:
  • GET  /admin/promptlab                    - HTML
  • GET  /admin/promptlab/status             - spisok shablonov/sessiy
  • POST /admin/promptlab/save_template      - {name, template, vars, id?}
  • POST /admin/promptlab/preview            - {template, vars} → expand_grid (pervye 20)
  • POST /admin/promptlab/run                - {name?, tpl_id?, template?, vars, selector:{alias|req}, max_tokens?, temperature?}
  • POST /admin/promptlab/diff               - {session_id, a_id, b_id}
  • POST /admin/promptlab/mark_best          - {session_id, best_id}
  • POST /admin/promptlab/export             - {session_id, mount}

Mosty:
- Yavnyy (UX ↔ Orkestratsiya): ves tsikl A→B: podstanovki → zapusk → sravnenie → vybor → eksport.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): unified-diff i fiksirovannaya setka obespechivayut vosproizvodimost.
- Skrytyy 2 (Praktika ↔ Sovmestimost): uvazhenie AB-rezhima; yadro Ester ne trogaem.

Zemnoy abzats:
Eto «mikrolaboratoriya promptov»: udobno proveryat formulirovki, bystro sravnivat otvety i sokhranyat luchshiy rezultat.

# c=a+b
"""
from __future__ import annotations
import os, time
from flask import Blueprint, jsonify, render_template, request

from modules.prompts.storage import list_templates, save_template, list_sessions, get_session, save_session, export_session  # type: ignore
from modules.prompts.variations import plan_run, run_grid, diff_unified  # type: ignore
from modules.prompts.template_engine import expand_grid  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_pl = Blueprint("prompt_lab", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_pl.get("/admin/promptlab")
def page():
    return render_template("prompt_lab.html", ab=AB)

@bp_pl.get("/admin/promptlab/status")
def status():
    return jsonify({
        "ok": True, "ab": AB,
        "templates": list_templates(),
        "sessions": list_sessions()
    })

@bp_pl.post("/admin/promptlab/save_template")
def api_save_tpl():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "unnamed")
    tpl = str(body.get("template") or "")
    vars_spec = body.get("vars") or {}
    tpl_id = body.get("id")
    rep = save_template(name, tpl, vars_spec, tpl_id=tpl_id)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_pl.post("/admin/promptlab/preview")
def api_preview():
    body = request.get_json(silent=True) or {}
    tpl = str(body.get("template") or "")
    vars_spec = body.get("vars") or {}
    plan = plan_run(tpl, vars_spec, body.get("selector") or {})
    return jsonify({"ok": True, "result": plan})

@bp_pl.post("/admin/promptlab/run")
def api_run():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "session")
    tpl = str(body.get("template") or "")
    if not tpl and body.get("tpl_id"):
        # razreshim zapusk po sokhranennomu shablonu
        tpls = list_templates().get("items", [])
        for it in tpls:
            if it.get("id") == body.get("tpl_id"):
                tpl = it.get("template",""); 
                if not body.get("vars"):
                    body["vars"] = it.get("vars", {})
                name = it.get("name", name)
                break
    vars_spec = body.get("vars") or {}
    selector = body.get("selector") or {}
    max_tokens = int(body.get("max_tokens", 64))
    temperature = float(body.get("temperature", 0.0))
    if not tpl or not vars_spec:
        return jsonify({"ok": False, "error": "template/vars required"}), 400
    rep = run_grid(tpl, vars_spec, selector, max_tokens=max_tokens, temperature=temperature)
    if rep.get("dry"):
        return jsonify({"ok": True, "ab": AB, "result": rep})
    # sokhranit sessiyu
    sess = {
        "id": None,
        "name": name,
        "template": tpl,
        "vars": vars_spec,
        "selector": selector,
        "grid": expand_grid(tpl, vars_spec),
        "results": rep.get("results", []),
        "diffs": [],
        "best_id": None,
        "created": int(time.time())
    }
    sid = save_session(sess)["id"]
    return jsonify({"ok": True, "ab": AB, "session_id": sid, "result": {"count": len(sess["results"])}})

@bp_pl.post("/admin/promptlab/diff")
def api_diff():
    body = request.get_json(silent=True) or {}
    sid = (body.get("session_id") or "").strip()
    a_id = (body.get("a_id") or "").strip()
    b_id = (body.get("b_id") or "").strip()
    if not sid or not a_id or not b_id:
        return jsonify({"ok": False, "error": "session_id/a_id/b_id required"}), 400
    sess = get_session(sid)
    if not sess.get("ok"): return jsonify(sess), 404
    items = sess["session"].get("results", [])
    a = next((x for x in items if x.get("id")==a_id), None)
    b = next((x for x in items if x.get("id")==b_id), None)
    if not a or not b: return jsonify({"ok": False, "error":"ids-not-found"}), 404
    d = diff_unified(a.get("output",""), b.get("output",""), a_id, b_id)
    # sokhranit diff v sessii
    s = sess["session"]; diffs = list(s.get("diffs", [])); diffs.append(d); s["diffs"] = diffs
    save_session(s)
    return jsonify({"ok": True, "diff": d})

@bp_pl.post("/admin/promptlab/mark_best")
def api_mark_best():
    body = request.get_json(silent=True) or {}
    sid = (body.get("session_id") or "").strip()
    best_id = (body.get("best_id") or "").strip()
    if not sid or not best_id:
        return jsonify({"ok": False, "error": "session_id/best_id required"}), 400
    sess = get_session(sid)
    if not sess.get("ok"): return jsonify(sess), 404
    s = sess["session"]; s["best_id"] = best_id
    save_session(s)
    return jsonify({"ok": True, "best_id": best_id})

@bp_pl.post("/admin/promptlab/export")
def api_export():
    body = request.get_json(silent=True) or {}
    sid = (body.get("session_id") or "").strip()
    mount = (body.get("mount") or "").strip()
    if not sid or not mount:
        return jsonify({"ok": False, "error": "session_id/mount required"}), 400
    rep = export_session(sid, mount)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

def register_prompt_lab(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_pl)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("prompt_lab_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/promptlab")
        def _p(): return page()

        @pref.get("/admin/promptlab/status")
        def _s(): return status()

        @pref.post("/admin/promptlab/save_template")
        def _st(): return api_save_tpl()

        @pref.post("/admin/promptlab/preview")
        def _pr(): return api_preview()

        @pref.post("/admin/promptlab/run")
        def _r(): return api_run()

        @pref.post("/admin/promptlab/diff")
        def _d(): return api_diff()

        @pref.post("/admin/promptlab/mark_best")
        def _mb(): return api_mark_best()

        @pref.post("/admin/promptlab/export")
        def _e(): return api_export()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_pl)
    return app