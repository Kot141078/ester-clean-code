# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, time
from typing import Any
from flask import Blueprint, jsonify, request
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap
try:
    from modules.auth.rbac import has_any_role as _has_any_role
except Exception:
    def _has_any_role(_required):  # type: ignore
        return True
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers_admin_routes2", __name__)
_MEM_STATE: dict[str, Any] = {"active": "lmstudio", "configs": {}}
_ALLOWED = {"local", "lmstudio", "openai", "gemini", "anthropic", "cloud"}
_DEFAULT_CLOUD = "openai"

def _data_root() -> str:
    return (os.environ.get("ESTER_DATA_ROOT")
            or os.environ.get("ESTER_DATA_DIR")
            or os.path.join(os.getcwd(), "data"))

def _prov_dir() -> str:
    p = os.path.join(_data_root(), "app", "providers")
    os.makedirs(p, exist_ok=True)
    return p

def _active_path() -> str:
    return os.path.join(_prov_dir(), "active.json")

def _prov_cfg_path(name: str) -> str:
    return os.path.join(_prov_dir(), f"{name}.json")

def _read_json(path: str, default: Any) -> Any:
    global _MEM_STATE
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        if path.endswith("active.json"):
            return {"active": _MEM_STATE.get("active", "lmstudio")}
        if path.endswith(".json"):
            name = os.path.splitext(os.path.basename(path))[0]
            return dict((_MEM_STATE.get("configs") or {}).get(name) or {})
        return default

def _write_json(path: str, obj: Any) -> None:
    global _MEM_STATE
    if path.endswith("active.json") and isinstance(obj, dict):
        _MEM_STATE["active"] = str(obj.get("active") or obj.get("provider") or _MEM_STATE.get("active") or "lmstudio")
    elif path.endswith(".json") and isinstance(obj, dict):
        name = os.path.splitext(os.path.basename(path))[0]
        cfgs = _MEM_STATE.setdefault("configs", {})
        if isinstance(cfgs, dict):
            cfgs[name] = dict(obj)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        # read-only/locked FS: keep in-memory state for current process
        return

@bp.get("/providers/status")
def providers_status():
    active = _read_json(_active_path(), {})
    name = active.get("active") or active.get("provider") or "lmstudio"
    name = str(name).strip().lower() or "lmstudio"
    if name == "cloud":
        name = _DEFAULT_CLOUD
    cfg = _read_json(_prov_cfg_path(name), {})
    providers = ["local", "lmstudio", "openai", "gemini", "anthropic"]
    ret = {
        "ok": True,
        "active": name,
        "active_provider": name,
        "providers": providers,
        "available": providers,
        "default_cloud": _DEFAULT_CLOUD,
        "lmstudio": True,
        "config": {
            "base_url": cfg.get("base_url"),
            "model": cfg.get("model"),
            "mode": cfg.get("mode", "local" if name in {"lmstudio", "local"} else "cloud"),
        },
        "authoring_backend": "local",
    }
    if name == "lmstudio":
        import urllib.request
        base = cfg.get("base_url") or os.environ.get("LMSTUDIO_URL") or "http://127.0.0.1:1234/v1"
        try:
            with urllib.request.urlopen(base + "/models", timeout=1.5) as r:
                ret["lmstudio_probe"] = (200 <= r.status < 300)
        except Exception:
            ret["lmstudio_probe"] = False
    return jsonify(ret)

@bp.post("/providers/select")
@jwt_required()
def providers_select():
    body = request.get_json(silent=True) or {}
    provider = (body.get("provider") or body.get("name") or body.get("mode") or "").strip().lower()
    if not provider:
        return jsonify({"ok": False, "error": "provider is required"}), 400
    if provider == "cloud":
        provider = _DEFAULT_CLOUD
    if provider not in _ALLOWED:
        return jsonify({"ok": False, "error": "unknown provider"}), 400
    # Keep RBAC check after validation so invalid provider returns 400 for any role.
    if not _has_any_role(["provider_manager", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    cfg = {
        "provider": provider,
        "name": provider,
        "active": provider,
        "base_url": body.get("base_url"),
        "model": body.get("model"),
        "mode": body.get("mode") or ("local" if provider in {"lmstudio", "local"} else "cloud"),
        "ts": int(time.time()),
    }
    if body.get("api_key"):
        cfg["api_key"] = body["api_key"]
    _write_json(_active_path(), {"active": provider, "provider": provider, "name": provider})
    _write_json(_prov_cfg_path(provider), cfg)
    return jsonify({"ok": True, "active": provider, "saved": cfg})

@bp.get("/providers/models")
def providers_models():
    name = (request.args.get("provider")
            or _read_json(_active_path(), {}).get("active")
            or "lmstudio").lower()
    if name == "cloud":
        name = _DEFAULT_CLOUD
    cfg = _read_json(_prov_cfg_path(name), {})
    if name == "lmstudio":
        import urllib.request, json as _json
        base = cfg.get("base_url") or os.environ.get("LMSTUDIO_URL") or "http://127.0.0.1:1234/v1"
        try:
            with urllib.request.urlopen(base + "/models", timeout=1.8) as r:
                data = _json.loads(r.read().decode("utf-8", "ignore"))
            models = [m.get("id") or m.get("name") for m in data.get("data", []) if m]
            if not models:
                models = ["local-model"]
            return jsonify({"ok": True, "provider": name, "models": models, "source": "lmstudio"})
        except Exception as e:
            return jsonify({"ok": True, "provider": name, "models": ["local-model"], "source": "lmstudio", "error": str(e)})
    else:
        mdl = cfg.get("known_models") or ([cfg.get("model")] if cfg.get("model") else [])
        if not mdl:
            mdl = [f"{name}-default"]
        return jsonify({"ok": True, "provider": name, "models": mdl, "source": "config"})
