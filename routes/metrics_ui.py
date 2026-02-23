# -*- coding: utf-8 -*-
from __future__ import annotations

import time

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_ui = Blueprint("metrics_ui", __name__, url_prefix="/metrics")

@bp_metrics_ui.get("/ui")
def metrics_ui():
    rss = psutil.Process().memory_info().rss if psutil else 0  # type: ignore
    ctx = {
        "uptime_sec": int(time.time() - int(__import__("os").getenv("ESTER_BUILD_TS", str(int(time.time()))))),
        "rss": rss,
        "psutil": psutil is not None,
    }
    return render_template("metrics_ui.html", **ctx)



def register(app):
    app.register_blueprint(bp_metrics_ui)
    return app
