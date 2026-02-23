# -*- coding: utf-8 -*-
"""
routes.root_minimal - prostoy HTML-ekran s otchetom zagruzki.

MOSTY:
- Yavnyy: Predstavlenie ↔ Diagnostika - HTML-obertka nad tem zhe otchetom dlya bystrogo vizualnogo osmotra.
- Skrytyy 1: Infoteoriya - vizualizatsiya kak «deshifrator» sostoyaniya (umenshaem kognitivnuyu entropiyu).
- Skrytyy 2: Bayes - operator otsenivaet dostovernost «zdorovya» po artefaktam (zaregistrirovano/propuscheno).

ZEMNOY ABZATs:
Kak panel priborov v mashine: lampochki i tsifry - srazu vidno, edet li avtomobil i chto chinit.
"""
import html
from flask import Blueprint, current_app, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ui_min", __name__)

@bp.get("/ui")
def ui():
    info = current_app.config.get("ESTER_BOOT_INFO", {})
    def _fmt(obj):
        try:
            import json
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            return str(obj)
    body = f"""
    <html><head><meta charset="utf-8"><title>Ester • Safe Boot</title></head>
    <body>
      <h1>Ester • Safe Boot</h1>
      <pre>{html.escape(_fmt(info))}</pre>
    </body></html>
    """
    return Response(body, mimetype="text/html")
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app