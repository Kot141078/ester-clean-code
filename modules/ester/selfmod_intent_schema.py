# -*- coding: utf-8 -*-
"""
SelfModIntent schema for Ester.

Etot modul opisyvaet kontrakt bezopasnogo samoizmeneniya:
- gde Ester mozhet predlagat izmeneniya;
- kakie zony navsegda zaprescheny;
- kak proveryat predlozhennye izmeneniya pered vyzovom /ester/selfmod/propose.

Nikakikh realnykh izmeneniy sam po sebe modul ne delaet.
Ispolzuetsya mostami i routami-obertkami.
"""

import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Zhestkie zaprety: ne trogaem portal, kaskad i pamyat.
FORBIDDEN_PREFIXES = [
    "templates/portal.html",
    "templates/portal",
    "modules/memory/",
    "modules/thinking/cascade.py",
    "modules/thinking/cascade_closed.py",
]

# Bazovye bezopasnye zony dlya samoizmeneniya i rasshireniy.
ALLOWED_PREFIXES_DEFAULT = [
    "modules/ester/",
    "routes/ester_",
    "scripts/",
    "config/",
]


def get_mode() -> str:
    """AB-rezhim dlya logiki namereniy samoizmeneniya."""
    mode = (os.getenv("ESTER_SELFMOD_INTENT_AB", "A") or "A").strip().upper()
    return "B" if mode == "B" else "A"


def is_path_forbidden(path: str) -> bool:
    norm = path.replace("\\", "/")
    for bad in FORBIDDEN_PREFIXES:
        if norm == bad or norm.startswith(bad):
            return True
    return False


def is_path_allowed(path: str) -> bool:
    """Razreshaem tolko to, chto ne v stop-liste i lezhit v dozvolennykh prefiksakh."""
    norm = path.replace("\\", "/")
    if is_path_forbidden(norm):
        return False
    for pref in ALLOWED_PREFIXES_DEFAULT:
        if norm.startswith(pref):
            return True
    return False


def describe() -> Dict[str, Any]:
    """Chelovekochitaemyy profil samoizmeneniya dlya Ester i operatora."""
    mode = get_mode()
    return {
        "ok": True,
        "mode": mode,
        "sources": {
            "ester": {
                "allowed": True,
                "note": "Ester mozhet predlagat izmeneniya tolko cherez zaschischennyy kontur i v razreshennykh zonakh.",
            },
            "operator": {
                "allowed": True,
                "note": "Operator mozhet vyzyvat /ester/selfmod/propose napryamuyu, no guard vse ravno deystvuet.",
            },
        },
        "paths": {
            "allowed_prefixes": ALLOWED_PREFIXES_DEFAULT,
            "forbidden_prefixes": FORBIDDEN_PREFIXES,
        },
        "rules": {
            "no_hidden_daemons": True,
            "no_self_mod_without_consent": True,
            "network_only_via_will": True,
            "sisters_only_via_will": True,
        },
    }


def validate_proposal(source: str, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Proveryaem spisok izmeneniy pered fakticheskim vyzovom /ester/selfmod/propose.

    Vozvraschaem:
    {
      "ok": bool,
      "errors": [..],
      "guard": [
        {"idx": 0, "path": "...", "allowed": bool, "note": "ok|forbidden_path|no_path"}
      ]
    }
    """
    errors: List[str] = []
    guard: List[Dict[str, Any]] = []

    src = (source or "").strip() or "ester"

    for idx, ch in enumerate(changes or []):
        path = str(ch.get("path") or "")
        if not path:
            errors.append(f"change_{idx}_no_path")
            guard.append(
                {"idx": idx, "path": path, "allowed": False, "note": "no_path"}
            )
            continue

        if is_path_forbidden(path):
            errors.append(f"change_{idx}_forbidden:{path}")
            guard.append(
                {
                    "idx": idx,
                    "path": path,
                    "allowed": False,
                    "note": "forbidden_path",
                }
            )
            continue

        allowed = is_path_allowed(path)
        guard.append(
            {
                "idx": idx,
                "path": path,
                "allowed": bool(allowed),
                "note": "ok" if allowed else "forbidden_scope",
            }
        )
        if not allowed:
            errors.append(f"change_{idx}_forbidden_scope:{path}")

    return {"ok": not errors, "errors": errors, "guard": guard}