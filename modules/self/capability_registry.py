# -*- coding: utf-8 -*-
"""
modules/self/capability_registry.py — inventarizatsiya i reestr vozmozhnostey Ester (routy, deystviya, rasshireniya, flagi).

API:
  • snapshot(app=None) -> dict        # poluchit aktualnuyu kartu vozmozhnostey
  • register_capability(name, meta)   # yavnaya registratsiya iz novykh moduley (optsionalno)
  • counters() -> dict                # metriki

Mosty:
- Yavnyy: (Myshlenie ↔ Samopoznanie) predostavlyaem «kartu sebya» dlya voli/planirovschika.
- Skrytyy #1: (Kibernetika ↔ Kontrol) flagi A/B i primenennye rasshireniya vidny i proveryaemy.
- Skrytyy #2: (Infoteoriya ↔ Audit) zapis snapshota v fayl s sha256 i vremenem — osnova vosproizvodimosti.

Zemnoy abzats:
Eto kak inventarnaya vedomost: chto podklyucheno, kakie rychagi dostupny, kakie moduli zagruzheny — v odnom meste.

# c=a+b
"""
from __future__ import annotations

import hashlib, json, os, time
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_REG: Dict[str, Dict[str, Any]] = {}  # yavnye registratsii kapabiliti
_CNT = {"snapshots_total": 0}

def _sha256(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

def register_capability(name: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    _REG[name] = dict(meta or {})
    return {"ok": True}

def _routes_map(app) -> List[Dict[str, Any]]:
    out = []
    try:
        for rule in app.url_map.iter_rules():
            out.append({"rule": str(rule), "endpoint": rule.endpoint, "methods": sorted([m for m in rule.methods if m in ("GET","POST","PUT","DELETE")])})
    except Exception:
        pass
    return sorted(out, key=lambda x: x["rule"])

def _blueprints(app) -> List[str]:
    try:
        return sorted(list(app.blueprints.keys()))
    except Exception:
        return []

def _actions() -> List[Dict[str, Any]]:
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        return list_actions()
    except Exception:
        return []

def _extensions_state() -> Dict[str, Any]:
    root = os.getenv("SELF_CODE_ROOT", "extensions")
    enabled = os.path.join(root, "enabled")
    drafts = os.path.join(root, "drafts")
    def ls(p):
        try:
            return sorted([f for f in os.listdir(p) if f.endswith(".py")])
        except Exception:
            return []
    return {"root": os.path.abspath(root), "enabled": ls(enabled), "drafts": ls(drafts)}

def _ab_flags() -> Dict[str, Any]:
    import os
    return {
        "SELF_CAPS_AB": os.getenv("SELF_CAPS_AB", "A"),
        "SELF_PLAN_AB": os.getenv("SELF_PLAN_AB", "A"),
        "SELF_CODE_AB": os.getenv("SELF_CODE_AB", "A"),
    }

def snapshot(app=None) -> Dict[str, Any]:
    from flask import current_app
    app = app or current_app
    caps = {
        "ts": int(time.time()),
        "blueprints": _blueprints(app),
        "routes": _routes_map(app),
        "actions": _actions(),
        "explicit": dict(_REG),
        "extensions": _extensions_state(),
        "ab": _ab_flags(),
    }
    _CNT["snapshots_total"] += 1
    try:
        os.makedirs("data/self", exist_ok=True)
        with open("data/self/capabilities.json", "w", encoding="utf-8") as f:
            json.dump({"sha256": _sha256(caps), **caps}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return caps

def counters() -> Dict[str, int]:
    return dict(_CNT)