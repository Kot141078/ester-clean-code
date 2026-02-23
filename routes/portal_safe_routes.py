# D:\ester-project\routes/portal_safe_routes.py
# Polnyy fayl

from flask import Blueprint, Response, render_template, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("portal_safe", __name__, url_prefix="/_safe")

@bp.get("/portal")
def portal():
    try:
        return render_template("portal.html", config=current_app.config)
    except Exception as e:  # esli shablon nedostupen - otdaem prostoy HTML
        html = f"""<!doctype html><meta charset="utf-8"><title>/_safe/portal (fallback)</title>
        <h1>/_safe/portal - fallback</h1>
        <p>Oshibka rendera shablona: <code>{e}</code></p>"""
        return Response(html, mimetype="text/html")

def register(app):
    app.register_blueprint(bp)