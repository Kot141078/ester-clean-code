# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

empathy_bp = Blueprint("empathy", __name__, url_prefix="/empathy")


class _EmpathyModule:
    def __init__(self, user_id: str = "default_user", empathy_level: int = 6) -> None:
        self.user_id = str(user_id or "default_user")
        self.empathy_level = int(empathy_level or 6)
        self.user_history: List[Dict[str, Any]] = []
        self._load_from_disk()

    def _base_dir(self) -> Path:
        base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
        out = Path(base).resolve() / "empathy"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _path(self) -> Path:
        safe_uid = "".join(ch for ch in self.user_id if ch.isalnum() or ch in {"-", "_", "."}) or "default_user"
        return self._base_dir() / f"{safe_uid}.json"

    def _load_from_disk(self) -> None:
        p = self._path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            history = data.get("history") if isinstance(data, dict) else None
            if isinstance(history, list):
                self.user_history = [x for x in history if isinstance(x, dict)]
        except Exception:
            self.user_history = []

    def save_to_db(self) -> bool:
        payload = {
            "user_id": self.user_id,
            "empathy_level": self.empathy_level,
            "history": self.user_history[-200:],
            "saved_at": float(time.time()),
        }
        try:
            self._path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def analyze_user_message(self, message: str) -> Dict[str, Any]:
        text = str(message or "").strip()
        lower = text.lower()
        tone = "neutral"
        style = "standard"
        prefix = ""

        negative_markers = ["nepriyatno", "zlyu", "razdrazh", "plokho", "uzhas", "besit", "grust"]
        positive_markers = ["spasibo", "otlichno", "super", "klass", "rad", "khorosho"]

        if any(m in lower for m in negative_markers):
            tone = "negative"
            style = "empathetic"
            prefix = "I understand that this is unpleasant. Let's calmly take it apart and fix it."
        elif any(m in lower for m in positive_markers):
            tone = "positive"
            style = "warm"
            prefix = "Thanks for your feedback."

        result = {
            "tone": tone,
            "response_style": style,
            "prefix": prefix,
            "empathy_level": int(self.empathy_level),
        }
        self.user_history.append({"ts": float(time.time()), "message": text, "analysis": result})
        self.user_history = self.user_history[-200:]
        return result

    def generate_friendly_response(self, base_response: str, analysis: Dict[str, Any]) -> str:
        base = str(base_response or "").strip()
        prefix = str((analysis or {}).get("prefix") or "")
        suffix = ""
        if self.empathy_level >= 8:
            suffix = " Gotov pomoch do rezultata."
        return f"{prefix}{base}{suffix}".strip()

    def suggest_improvement(self) -> str:
        return "If you want, I can offer a softer and shorter answer."


_modules_by_user: Dict[str, _EmpathyModule] = {}


def _get_mod(user_id: str | None = None, empathy_level: int | None = None) -> _EmpathyModule:
    uid = str(user_id or "default_user")
    mod = _modules_by_user.get(uid)
    if mod is None:
        lvl = int(empathy_level if empathy_level is not None else int(os.getenv("EMPATHY_DEFAULT_LEVEL", "6") or 6))
        mod = _EmpathyModule(user_id=uid, empathy_level=lvl)
        _modules_by_user[uid] = mod
    elif empathy_level is not None:
        mod.empathy_level = int(empathy_level)
    return mod


@empathy_bp.get("/ping")
@jwt_required(optional=True)
def empathy_ping():
    mod = _get_mod()
    return jsonify({"ok": True, "user": mod.user_id, "level": int(mod.empathy_level)})


@empathy_bp.post("/analyze")
@jwt_required()
def empathy_analyze():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    level = data.get("empathy_level")
    message = str(data.get("message") or data.get("text") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "empty message"}), 400

    mod = _get_mod(user_id=user_id, empathy_level=int(level) if level is not None else None)
    analysis = mod.analyze_user_message(message)
    return jsonify({"ok": True, "result": analysis, "analysis": analysis})


@empathy_bp.post("/tune")
@jwt_required()
def empathy_tune():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    base = str(data.get("base") or "").strip()
    if not base:
        return jsonify({"ok": False, "error": "empty base"}), 400
    mod = _get_mod(data.get("user_id"))
    analysis = data.get("analysis") or {}
    text = mod.generate_friendly_response(base, analysis if isinstance(analysis, dict) else {})
    return jsonify({"ok": True, "text": text})


@empathy_bp.post("/apply")
@jwt_required()
def empathy_apply():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    level = data.get("empathy_level")
    message = str(data.get("user_message") or data.get("message") or "").strip()
    base = str(data.get("base_response") or data.get("base") or "").strip()
    if not base:
        return jsonify({"ok": False, "error": "empty base_response"}), 400

    mod = _get_mod(user_id=user_id, empathy_level=int(level) if level is not None else None)
    analysis = data.get("analysis")
    if not isinstance(analysis, dict):
        analysis = mod.analyze_user_message(message)
    response = mod.generate_friendly_response(base, analysis)
    return jsonify({"ok": True, "response": response, "analysis": analysis})


@empathy_bp.get("/status")
@jwt_required()
def empathy_status():
    user_id = request.args.get("user_id")
    mod = _get_mod(user_id=user_id)
    return jsonify(
        {
            "ok": True,
            "user_id": mod.user_id,
            "empathy_level": int(mod.empathy_level),
            "history_len": int(len(mod.user_history)),
        }
    )


@empathy_bp.post("/save")
@jwt_required()
def empathy_save():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    mod = _get_mod(data.get("user_id"))
    ok = mod.save_to_db()
    if ok:
        return jsonify({"ok": True, "saved": True})
    return jsonify({"ok": False, "saved": False, "error": "save_failed"}), 500


@empathy_bp.get("/suggest")
@jwt_required(optional=True)
def empathy_suggest():
    mod = _get_mod(request.args.get("user_id"))
    return jsonify({"ok": True, "suggestion": mod.suggest_improvement()})


def register_empathy_routes(app, url_prefix: str = "/empathy"):
    if url_prefix != "/empathy":
        alt = Blueprint("empathy_alt", __name__, url_prefix=url_prefix)
        for rule in empathy_bp.deferred_functions:
            rule(alt)
        app.register_blueprint(alt)
        return app
    app.register_blueprint(empathy_bp)
    return app


def register(app):
    return register_empathy_routes(app)


def init_app(app):
    return register_empathy_routes(app)


__all__ = ["empathy_bp", "register", "init_app", "register_empathy_routes"]
