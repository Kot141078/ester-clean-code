# -*- coding: utf-8 -*-
"""routes/metrics_prom.py - Prometheus text exposure endpoint (v0.0.4 format).

Name:
  - Gavat scrape-sovmestimye metriki bez avtorizatsii.
  - Ne konfliktovat s istoricheskim JSON /metrics (s JWT).

Route:
  GET /metrics/prom -> text/plain; version=0.0.4

Sostav metrik (minimalnyy nabor dlya SLO-pravil i nablyudaemosti):
  - ester_uptime_seconds (gauge)
  - ester_process_rss_bytes (gauge)
  - ester_cpu_percent (gauge)
  - ester_build_info{version,commit} 1 (gauge s leyblami)
  - ester_backup_last_success_timestamp_seconds (gauge; iz ENV, inache = start_time)

ENV:
  ESTER_BUILD_VERSION, ESTER_BUILD_COMMIT, ESTER_BACKUP_LAST_SUCCESS_TS"""
from __future__ import annotations

import os
import time

import psutil
from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_prom = Blueprint("metrics_prom", __name__)

_START_TS = time.time()
_VERSION = os.getenv("ESTER_BUILD_VERSION", os.getenv("VERSION", "unknown"))
_COMMIT = os.getenv("ESTER_BUILD_COMMIT", os.getenv("GIT_COMMIT", "unknown"))


def _number(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _render() -> str:
    rss = psutil.Process().memory_info().rss
    cpu = psutil.cpu_percent()
    backup_ts = _number(os.getenv("ESTER_BACKUP_LAST_SUCCESS_TS") or _START_TS)

    lines = []
    lines.append("# HELP ester_uptime_seconds Uptime of the Ester process in seconds.")
    lines.append("# TYPE ester_uptime_seconds gauge")
    lines.append("ester_uptime_seconds {:.0f}".format(_number(time.time() - _START_TS)))

    lines.append("# HELP ester_process_rss_bytes Resident set size of the Ester process.")
    lines.append("# TYPE ester_process_rss_bytes gauge")
    lines.append("ester_process_rss_bytes {:.0f}".format(rss))

    lines.append("# HELP ester_cpu_percent CPU percent sampled by psutil.")
    lines.append("# TYPE ester_cpu_percent gauge")
    lines.append("ester_cpu_percent {:.2f}".format(cpu))

    # Build info with labels
    lines.append("# HELP ester_build_info Build information for Ester.")
    lines.append("# TYPE ester_build_info gauge")
    lines.append('ester_build_info{{version="{}",commit="{}"}} 1'.format(_VERSION, _COMMIT))

    # Backup timestamp (seconds since epoch)
    lines.append(
        "# HELP ester_backup_last_success_timestamp_seconds Unix timestamp of last successful backup."
    )
    lines.append("# TYPE ester_backup_last_success_timestamp_seconds gauge")
    lines.append("ester_backup_last_success_timestamp_seconds {:.0f}".format(backup_ts))

    return "\n".join(lines) + "\n"


@bp_metrics_prom.get("/metrics")
@bp_metrics_prom.get("/metrics/prom")
def metrics_prom():
    body = _render()
    return Response(body, status=200, mimetype="text/plain; version=0.0.4; charset=utf-8")


def register(app):
    if bp_metrics_prom.name not in getattr(app, "blueprints", {}):
        app.register_blueprint(bp_metrics_prom)
    return app
