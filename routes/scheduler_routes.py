# -*- coding: utf-8 -*-
"""
routes/scheduler_routes.py — REST API dlya upravleniya zadachami v planirovschike.

Etot modul predostavlyaet HTTP-endpointy dlya sozdaniya, prosmotra, otmeny i prinuditelnogo
zapuska zaplanirovannykh zadach. Bse endpointy zaschischeny s pomoschyu JWT.

Klyuchevye vozmozhnosti:
- Sozdanie zadach s ukazaniem tipa, deystviya i pravila povtoreniya (rrule).
- Prosmotr spiska vsekh aktivnykh zadach.
- Otmena zaplanirovannoy zadachi po ee ID.
- Prinuditelnyy zapusk zadach, vremya kotorykh podoshlo.
- Modul imeet "myagkuyu" zavisimost ot dvizhka planirovschika i budet vozvraschat
  oshibku 503, esli dvizhok nedostupen.

R egistratsiya v prilozhenii Flask:
  from routes.scheduler_routes import register_scheduler_routes
  register_scheduler_routes(app, url_prefix="/tasks")

Endpointy:
  POST /tasks/create     — Sozdanie zadachi. Telo: {kind, action, rrule, payload}
  GET  /tasks/list       — Poluchenie spiska zadach.
  POST /tasks/cancel      — Otmena zadachi. Telo: {task_id}
  POST /tasks/run_due     — Zapusk prosrochennykh zadach. Telo: {now_ts?}
"""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Popytka importa funktsiy iz dvizhka planirovschika.
# Esli import ne udalsya, API vernet oshibku o nedostupnosti servisa.
try:
    from modules.scheduler_engine import cancel_task, create_task, list_tasks, run_due

    SCHEDULER_AVAILABLE = True
except ImportError:
    cancel_task = create_task = list_tasks = run_due = None  # type: ignore
    SCHEDULER_AVAILABLE = False


def register_scheduler_routes(app, url_prefix: str = "/tasks"):
    """
    R egistriruet marshruty API planirovschika v prilozhenii Flask.

    Args:
        app: Ekzemplyar prilozheniya Flask.
        url_prefix: Prefiks URL dlya vsekh marshrutov etogo modulya.
    """

    def _check_scheduler_availability():
        """Vozvraschaet otvet ob oshibke, esli planirovschik nedostupen."""
        if not SCHEDULER_AVAILABLE:
            return jsonify({"ok": False, "error": "scheduler_unavailable"}), 503
        return None

    @app.post(f"{url_prefix}/create")
    @jwt_required()
    def tasks_create():
        """Sozdaet novuyu zadachu v planirovschike."""
        if error_response := _check_scheduler_availability():
            return error_response

        data = request.get_json(silent=True) or {}
        kind = (data.get("kind") or "").strip()
        action = (data.get("action") or "").strip()
        rrule = (data.get("rrule") or "").strip()
        payload = data.get("payload") or {}

        if not kind or not action or not rrule:
            return (
                jsonify({"ok": False, "error": "kind, action, and rrule are required"}),
                400,
            )

        if not isinstance(payload, dict):
            payload = {"value": payload}

        try:
            task = create_task(kind, action, rrule, payload)
            return jsonify({"ok": True, "task": task}), 201
        except Exception as e:
            # Predpolagaetsya, chto 'app.logger' nastroen
            app.logger.error(f"Failed to create task: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.get(f"{url_prefix}/list")
    @jwt_required()
    def tasks_list():
        """Vozvraschaet spisok vsekh zaplanirovannykh zadach."""
        if error_response := _check_scheduler_availability():
            return error_response

        try:
            tasks = list_tasks()
            return jsonify({"ok": True, "tasks": tasks})
        except Exception as e:
            app.logger.error(f"Failed to list tasks: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post(f"{url_prefix}/cancel")
    @jwt_required()
    def tasks_cancel():
        """Otmenyaet zadachu po ee identifikatoru."""
        if error_response := _check_scheduler_availability():
            return error_response

        data = request.get_json(silent=True) or {}
        task_id = (data.get("task_id") or data.get("id") or "").strip()

        if not task_id:
            return jsonify({"ok": False, "error": "task_id is required"}), 400

        try:
            result = cancel_task(task_id)
            if result.get("ok") is False and result.get("error"):
                return jsonify(result), 404  # Zadacha ne naydena
            return jsonify({"ok": True, "task": result})
        except Exception as e:
            app.logger.error(f"Failed to cancel task {task_id}: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post(f"{url_prefix}/run_due")
    @jwt_required()
    def tasks_run_due():
        """Zapuskaet vse zadachi, vremya vypolneniya kotorykh nastupilo."""
        if error_response := _check_scheduler_availability():
            return error_response

        data = request.get_json(silent=True) or {}
        now_ts = data.get("now_ts")

        try:
            # Preobrazovanie vo float, esli now_ts peredano
            timestamp = float(now_ts) if now_ts is not None else None
            result = run_due(now_ts=timestamp)
            return jsonify(result)
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "Invalid now_ts format"}), 400
        except Exception as e:
            app.logger.error(f"Failed to run due tasks: {e}")
# return jsonify({"ok": False, "error": str(e)}), 500


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # vyzyvaem suschestvuyuschiy register_scheduler_routes(app) (url_prefix beretsya po umolchaniyu vnutri funktsii)
    return register_scheduler_routes(app)

# === /AUTOSHIM ===