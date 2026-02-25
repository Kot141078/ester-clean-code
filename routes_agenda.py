# -*- coding: utf-8 -*-
"""Agenda: viewing and simple actions (Acceptance, Dismiss, Snooze).
Memory store items as ZZF0Z."""
from __future__ import annotations

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Trying to import ZhVT, if it doesn’t exist, use a stub (Local Mode)
try:
    from flask_jwt_extended import jwt_required, get_jwt_identity
except ImportError:
    # Dummy decorator, just calls a function
    def jwt_required():
        def wrapper(fn):
            return fn
        return wrapper
    def get_jwt_identity():
        return "local_user"

AGENDA_FILE = os.path.join("memory", "agenda.json")

class AgendaManager:
    """Local case manager.
    Store the state in memory/agenda.zsion."""
    def __init__(self):
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(AGENDA_FILE), exist_ok=True)
        if not os.path.exists(AGENDA_FILE):
            with open(AGENDA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load(self) -> List[Dict]:
        try:
            with open(AGENDA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, data: List[Dict]):
        with open(AGENDA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_agenda(self, user: str) -> List[Dict]:
        """Returns only active (pending) tasks."""
        all_items = self._load()
        # Filter: pending status and (if there is snooze) snooze time has expired
        active = []
        now = time.time()
        for item in all_items:
            if item.get("status") != "pending":
                continue
            if item.get("snooze_until") and item["snooze_until"] > now:
                continue
            active.append(item)
        
        # Sortirovka po prioritetu (vysokiy prioritet — vyshe)
        active.sort(key=lambda x: x.get("priority", 0), reverse=True)
        return active

    def update_status(self, item_id: str, status: str, snooze_min: int = 0) -> bool:
        items = self._load()
        found = False
        for item in items:
            if str(item.get("id")) == str(item_id):
                item["status"] = status
                if status == "snoozed":
                    # Stavim status obratno v pending, no s zaderzhkoy
                    item["status"] = "pending"
                    item["snooze_until"] = time.time() + (snooze_min * 60)
                item["updated_at"] = time.time()
                found = True
                break
        if found:
            self._save(items)
        return found

    def add_item(self, title: str, reason: str = "", priority: int = 1):
        """Method for adding a task (for example, from Telegram)."""
        items = self._load()
        new_item = {
            "id": f"task_{int(time.time())}_{len(items)}",
            "title": title,
            "reason": reason,
            "priority": priority,
            "status": "pending",
            "created_at": time.time()
        }
        items.append(new_item)
        self._save(items)
        return new_item["id"]

    def smoketest(self) -> str:
        """Checking file access."""
        try:
            self._ensure_storage()
            self._load()
            return "OK (Storage accessible)"
        except Exception as e:
            return f"FAILED: {e}"


# Global instance manager (Singleton for module)
agenda_manager = AgendaManager()

def register_agenda_routes(app, memory_manager=None, url_prefix="/agenda"):
    """Registration of routes. 
    memory_manager is passed for compatibility, but by default uses its local one."""
    manager = memory_manager if memory_manager else agenda_manager
    bp = Blueprint("agenda", __name__)

    @bp.get(url_prefix + "/today")
    @jwt_required()
    def today():
        # Podderzhka query param ?user=Owner
        user = request.args.get("user", "Owner")
        try:
            items = manager.get_agenda(user)
        except Exception as e:
            logging.error(f"[Agenda] Error getting items: {e}")
            items = []
        return jsonify({"agenda": items})

    @bp.post(url_prefix + "/accept")
    @jwt_required()
    def accept():
        data = request.get_json() or {}
        item_id = data.get("id")
        ok = manager.update_status(item_id, "done")
        return jsonify({"ok": ok})

    @bp.post(url_prefix + "/dismiss")
    @jwt_required()
    def dismiss():
        data = request.get_json() or {}
        item_id = data.get("id")
        ok = manager.update_status(item_id, "dismissed")
        return jsonify({"ok": ok})

    @bp.post(url_prefix + "/snooze")
    @jwt_required()
    def snooze():
        data = request.get_json() or {}
        item_id = data.get("id")
        minutes = int(data.get("minutes", 30))
        ok = manager.update_status(item_id, "snoozed", snooze_min=minutes)
        return jsonify({"ok": ok})

    app.register_blueprint(bp)
    logging.info(f"[Agenda] Routes registered at {url_prefix}")

# For compatibility with HelpnChesk
def smoketest():
    return agenda_manager.smoketest()