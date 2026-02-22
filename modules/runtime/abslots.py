# -*- coding: utf-8 -*-
"""
modules/runtime/abslots.py — upravlenie A/B-slotami rantayma (sovmestimostnyy fasad).

Mosty:
- Yavnyy: (Runtime A/B ↔ Edinoe yadro) API sokhranen, logika pereklyucheniya/deploya unifitsirovana.
- Skrytyy #1: (Profile ↔ Audit) sobytiya pomechayutsya yadrom odinakovo dlya vsekh fasadov.
- Skrytyy #2: (Komponenty ↔ Runtime) status vozvraschaet i aktivnyy slot, i sostoyanie komponentnykh slotov.

Zemnoy abzats:
Ostavlyaem te zhe funktsii (`status/deploy/health/switch`), no obschaya realizatsiya — menshe dreyfa i syurprizov.
# c=a+b
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional

from .ab_unified import (
    runtime_status as _status,
    runtime_deploy as _deploy,
    runtime_health as _health,
    runtime_switch as _switch,
)

def status() -> Dict[str, Any]:
    return _status()

def deploy(slot: str, zip_path: str) -> Dict[str, Any]:
    return _deploy(slot, zip_path)

def health(paths: Optional[List[str]] = None) -> Dict[str, Any]:
    return _health(paths)

def switch(slot: str, dry_run: bool = False, require_health: bool = True,
           override_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    return _switch(slot, dry_run=dry_run, require_health=require_health, override_paths=override_paths)
