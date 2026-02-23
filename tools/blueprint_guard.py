# -*- coding: utf-8 -*-
"""
tools.blueprint_guard — bezopasnaya registratsiya blyuprintov (dlya verify-rezhima).

MOSTY:
- Yavnyy: (Flask ↔ Registratsiya) install_blueprint_guard() podmenyaet register_blueprint.
- Skrytyy #1: (Diagnostika ↔ Ustoychivost) proglatyvaet povtornuyu registratsiyu.
- Skrytyy #2: (Logi ↔ Prozrachnost) pechataet preduprezhdenie v stderr.

ZEMNOY ABZATs:
Verifikator prokhodit skvoz «povtornye provoda» ne ostanavlivaya sborku.

# c=a+b
"""
from __future__ import annotations
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from flask import Flask  # type: ignore
except Exception as e:
    raise SystemExit(f"[blueprint_guard] cannot import Flask: {e}")

def install_blueprint_guard() -> None:
    if getattr(Flask, "register_blueprint__safe", False):
        return
    _ORIG = Flask.register_blueprint

    def _safe_register(self: "Flask", bp, *args, **kwargs):
        try:
            return _ORIG(self, bp, *args, **kwargs)
        except Exception as e:
            s = str(e)
            if "already registered" in s or "is already registered" in s or "The name" in s:
                print(f"[usercustomize.guard] skip duplicate blueprint: {getattr(bp,'name','bp')}", file=sys.stderr)
                return None
            raise

    Flask.register_blueprint = _safe_register  # type: ignore[attr-defined]
    setattr(Flask, "register_blueprint__safe", True)

# c=a+b