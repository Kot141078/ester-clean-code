# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

metrics_ui_bp = Blueprint("metrics_ui_routes", __name__)  # unikalnoe imya

@metrics_ui_bp.get("/metrics/ui")
def metrics_ui_index():
    try:
        return render_template("metrics_ui.html")
    except Exception:
        return "<html><body><h3>Metrics UI</h3></body></html>"

@metrics_ui_bp.get("/metrics/ui/")
def metrics_ui_index_slash():
    return metrics_ui_index()

def register_metrics_ui(app, url_prefix: str | None = None) -> None:
    if metrics_ui_bp.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(metrics_ui_bp)
    if url_prefix:
        # Dopolnitelno produbliruem pod zadannym prefiksom
        bp2 = Blueprint("metrics_ui_routes_prefixed", __name__, url_prefix=url_prefix)  # type: ignore
        bp2.add_url_rule("/metrics/ui", view_func=metrics_ui_index)
        bp2.add_url_rule("/metrics/ui/", view_func=metrics_ui_index_slash)
        if bp2.name not in getattr(app, "blueprints", {}):
            app.register_blueprint(bp2)

# Sovmestimost
def register(app) -> None:
    register_metrics_ui(app)


def register(app):
    app.register_blueprint(metrics_ui_bp)
    return app