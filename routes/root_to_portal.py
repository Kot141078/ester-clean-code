# -*- coding: utf-8 -*-
# Redirekt kornya "/" na portal "/portal" bez lomki kontraktov.
# A/B-slot: ROOT_REDIRECT_MODE = A|B (po umolchaniyu A).
#   A -> 302 na /portal (s sokhraneniem querystring)
#   B -> JSON {"ok": true, "goto": "/portal"} i nikakogo redirekta.
# Auto-fallback: If the application already has a "/" route, we DO NOT add a rule.
# Mosty: [yavnyy] HTTP/WSGI redirect -> UI /portal;
#        hide Integration with Flask Blueprince; stability when autoloading Rut/*.
# Earthly paragraph: we save clicks - the user goes directly to the portal, bypassing the service page.
from flask import Blueprint, redirect, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("root_to_portal", __name__)

def _mode():
    import os
    m = (os.environ.get("ROOT_REDIRECT_MODE") or "A").upper()
    return "B" if m == "B" else "A"

def _root_view():
    if _mode() == "B":
        return jsonify(ok=True, goto="/portal")
    qs = request.query_string.decode("utf-8")
    dest = "/portal" + (("?" + qs) if qs else "")
    return redirect(dest, code=302)

def _app_has_root(app):
    try:
        for r in app.url_map.iter_rules():
            if r.rule == "/":
                return True
    except Exception:
        pass
    return False

@bp.record_once
def _register_on_app(state):
    # We register the rule "/" ONLY if it does not exist yet - so as not to catch a conflict.
    try:
        app = state.app
        if not _app_has_root(app):
            app.add_url_rule("/", endpoint="__root_to_portal__", view_func=_root_view)
    except Exception:
        # Tikhiy feyl = avto-otkat.
        pass

# final line for acceptance:
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app