# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional
import os
import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

# SINGLE source: trying to use the roster, but with soft fullbacks
from providers.registry import ProviderRegistry  # type: ignore
try:
    from modules.auth.rbac import has_any_role as _has_any_role
except Exception:
    def _has_any_role(_required):  # type: ignore
        return True
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers", __name__)

# --- vspomogatelnye puti ---
def _data_root() -> Optional[str]:
    return os.environ.get("ESTER_DATA_ROOT") or os.environ.get("ESTER_DATA_DIR")

def _active_store_path() -> Optional[str]:
    dr = _data_root()
    if not dr:
        return None
    return os.path.join(dr, "app", "providers", "active.json")

def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)

# --- folbek-proba LM Studio (ne khodim v set) ---
def _probe_lmstudio() -> Optional[bool]:
    try:
        dr = _data_root()
        if not dr:
            return None
        path = os.path.join(dr, "app", "providers", "lmstudio_probe.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            v = obj.get("ok")
            return bool(v) if isinstance(v, bool) else None
    except Exception:
        pass
    return None

# --- universalnye obertki k reestru ---
def _reg() -> ProviderRegistry:
    return ProviderRegistry()  # type: ignore

def _get_active_from_reg(pr: Any) -> Optional[str]:
    # support for different implementations
    for key in ("active", "get_active"):
        if hasattr(pr, key) and callable(getattr(pr, key)):
            try:
                val = getattr(pr, key)()
                if isinstance(val, str) and val:
                    return val
            except Exception:
                pass
    # status() → {"active": "..."}
    if hasattr(pr, "status") and callable(getattr(pr, "status")):
        try:
            st = pr.status()
            if isinstance(st, dict):
                v = st.get("active") or st.get("active_provider")
                if isinstance(v, str) and v:
                    return v
        except Exception:
            pass
    # svoystvo?
    for prop in ("active", "active_provider"):
        v = getattr(pr, prop, None)
        if isinstance(v, str) and v:
            return v
    return None

def _set_active_in_reg(pr: Any, name: str) -> Optional[str]:
    # maksimalno myagko
    for key in ("select", "set_active", "use"):
        if hasattr(pr, key) and callable(getattr(pr, key)):
            try:
                res = getattr(pr, key)(name)
                # if select() returns dist - pull out the asset
                if isinstance(res, dict):
                    v = res.get("active") or res.get("active_provider")
                    if isinstance(v, str) and v:
                        return v
                # if you haven’t returned anything, we consider what you asked for active
                return name
            except Exception:
                pass
    return None

def _get_active_from_file() -> Optional[str]:
    path = _active_store_path()
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        v = obj.get("active")
        return v if isinstance(v, str) and v else None
    except Exception:
        return None

def _set_active_to_file(name: str) -> None:
    path = _active_store_path()
    if not path:
        return
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"active": name}, f, ensure_ascii=False, indent=2)

# --- marshruty ---
@bp.get("/providers/status")
def providers_status():
    pr = _reg()
    active = _get_active_from_reg(pr) or _get_active_from_file() or "lmstudio"
    return jsonify({
        "ok": True,
        "active_provider": active,
        "lmstudio_probe": _probe_lmstudio(),
        "authoring_backend": "local",
    })

@bp.post("/providers/select")
@jwt_required()
def providers_select():
    if not _has_any_role(["provider_manager", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    name = (data.get("name") or data.get("provider") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "empty name"}), 400

    pr = _reg()
    # 1) we try through the registry
    active = _set_active_in_reg(pr, name)
    # 2) mirror into a state file (single source for UI/status)
    _set_active_to_file(active or name)

    # 3) perechityvaem «istinu»
    final_active = _get_active_from_reg(pr) or _get_active_from_file() or name
    return jsonify({"ok": True, "active": final_active})


@bp.get("/providers/select")
@jwt_required()
def providers_select_status():
    if not _has_any_role(["provider_manager", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    pr = _reg()
    active = _get_active_from_reg(pr) or _get_active_from_file() or "lmstudio"
    return jsonify({"ok": True, "active": active})

@bp.get("/providers/models")
def providers_models():
    pr = _reg()
    active = _get_active_from_reg(pr) or _get_active_from_file() or "lmstudio"
    return jsonify({"ok": True, "provider": active, "models": []})
