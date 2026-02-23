
# -*- coding: utf-8 -*-
"""
sitecustomize.py — robust runtime shim for Ester (autoloaded by Python).
Mosty:
- Yavnyy: Staryy discover ↔ routy (aliasy scan_modules/get_status).
- Skrytyy #1: jupytext(...) → flask.jsonify(...).
- Skrytyy #2: ENV-most LMSTUDIO_BASE_URL ← LMSTUDIO_URL.
Zemnoy abzats: kladem etot fayl tak, chtoby on garantirovanno podkhvatyvalsya dazhe esli start idet iz tools/.
c=a+b
"""
from __future__ import annotations
import os, sys, importlib, types
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Marker, chtoby mozhno bylo proverit zagruzku
os.environ.setdefault("ESTER_SITE_HOOK", "1")

# --- jupytext → jsonify ---
try:
    import builtins
    def jupytext(payload=None, *args, **kwargs):  # type: ignore
        try:
            from flask import jsonify, Response
            try:
                return jsonify(payload)
            except Exception:
                import json as _json
                return Response(_json.dumps(payload or {}), mimetype="application/json")
        except Exception:
            return payload
    builtins.jupytext = jupytext  # type: ignore[attr-defined]
except Exception:
    pass

# --- ENV most ---
if not os.getenv("LMSTUDIO_BASE_URL") and os.getenv("LMSTUDIO_URL"):
    os.environ["LMSTUDIO_BASE_URL"] = os.environ["LMSTUDIO_URL"]

# --- Patch discover (neskolko vozmozhnykh putey) ---
_TARGETS = [
    "modules.app.discover",
    "ester.modules.app.discover",
    "app.discover",
    "modules.discover",
    "discover",
]

def _patch_discover_module(m: types.ModuleType) -> None:
    try:
        if not hasattr(m, "scan_modules") and hasattr(m, "scan"):
            setattr(m, "scan_modules", getattr(m, "scan"))
        if not hasattr(m, "get_status") and hasattr(m, "status"):
            setattr(m, "get_status", getattr(m, "status"))
    except Exception:
        pass

# 1) Patch uzhe zagruzhennykh
for name, mod in list(sys.modules.items()):
    if name in _TARGETS and isinstance(mod, types.ModuleType):
        _patch_discover_module(mod)

# 2) Poprobovat importirovat i propatchit, esli dostupno
for name in list(_TARGETS):
    try:
        m = importlib.import_module(name)
        _patch_discover_module(m)
    except Exception:
        pass

# 3) Ustanovit import-khuk, chtoby patch primenyalsya pri buduschikh importakh
try:
    import importlib.abc, importlib.util  # type: ignore
    class _DiscoverFinder(importlib.abc.MetaPathFinder):  # type: ignore
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in _TARGETS:
                return None
            spec = importlib.util.find_spec(fullname)
            if not spec or not spec.loader:
                return None
            orig_loader = spec.loader
            class _Loader(importlib.abc.Loader):  # type: ignore
                def create_module(self, spec):
                    if hasattr(orig_loader, "create_module"):
                        return orig_loader.create_module(spec)  # type: ignore
                    return None
                def exec_module(self, module):
                    orig_loader.exec_module(module)  # type: ignore
                    try:
                        _patch_discover_module(module)
                    except Exception:
                        pass
            spec.loader = _Loader()
            return spec
    sys.meta_path.insert(0, _DiscoverFinder())
except Exception:
    pass