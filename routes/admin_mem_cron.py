# -*- coding: utf-8 -*-
"""
routes/admin_mem_cron.py - REST-obertka dlya nochnykh tekhprotsedur pamyati (heal/compact/snapshot/reindex).

Endpointy:
  • POST /admin/mem/cron/run {"tasks":["heal","compact","snapshot","reindex"]} → otchet
  • GET  /metrics/mem_maintenance → Prometheus-tekst

Mosty:
- Yavnyy: (Memory ↔ Ekspluatatsiya) Zapuskaem protsedury bez skrytykh fonovykh demonov.
- Skrytyy #1: (Infoteoriya ↔ Planirovanie) Prostoy otchet prigoden dlya deshevogo dashborda - nizkaya entropiya interfeysa.
- Skrytyy #2: (Kibernetika ↔ Volya) Mozhet vyzyvatsya po raspisaniyu iz RuleHub/planirovschika, povyshaya upravlyaemost.

Zemnoy abzats:
Eto «vyklyuchatel uborschika»: nazhal - i poshel tsikl obsluzhivaniya pamyati. Tochki kontrolya: otchet JSON i schetchiki Prometheus.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mem_maintenance = Blueprint("mem_maintenance", __name__)

# Drop-in import: esli otsutstvuet - otrabatyvaem myagko
try:
    from scheduler.cron_memory_maintenance import run_pipeline, counters  # type: ignore
except Exception:  # pragma: no cover
    run_pipeline = counters = None  # type: ignore


def register(app):  # pragma: no cover
    """Registratsiya blyuprinta (drop-in)."""
    app.register_blueprint(bp_mem_maintenance)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


@bp_mem_maintenance.route("/admin/mem/cron/run", methods=["POST"])
def api_run():
    """Zapustit odin ili neskolko etapov obsluzhivaniya pamyati."""
    if run_pipeline is None:
        return jsonify({"ok": False, "error": "maintenance unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    tasks: List[str] = list(data.get("tasks") or ["heal", "compact", "snapshot"])
    # Kontrakt ne menyaem: vozvraschaem to, chto vernul payplayn
    return jsonify(run_pipeline(tasks))


def _prom_headers() -> Tuple[str, int, Dict[str, str]]:
    """Edinye zagolovki Prometheus exposition format."""
    return "", 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}


@bp_mem_maintenance.route("/metrics/mem_maintenance", methods=["GET"])
def metrics():
    """Schetchiki po tekhprotseduram pamyati v formate Prometheus."""
    body_lines: List[str] = []
    if counters is None:
        body_lines = [
            "mem_maintenance_runs_total 0",
            "mem_maintenance_steps_ok 0",
            "mem_maintenance_steps_fail 0",
        ]
    else:
        c = counters()
        body_lines = [
            f"mem_maintenance_runs_total {int(c.get('runs_total', 0))}",
            f"mem_maintenance_steps_ok {int(c.get('steps_ok', 0))}",
            f"mem_maintenance_steps_fail {int(c.get('steps_fail', 0))}",
        ]

    body = "\n".join(body_lines) + "\n"
    # Vozvraschaem (body, status, headers) - korrektnyy troynoy kortezh dlya Flask
    return body, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}


__all__ = ["bp_mem_maintenance", "register", "init_app"]