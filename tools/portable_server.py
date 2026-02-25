# -*- coding: utf-8 -*-
"""tools/portable_server.py - perenosimyy mini-server Ester dlya zapuska pryamo s fleshki.

Zapusk:
  $ python tools/portable_server.py
  (or run_ester_portable.sh/cmd, sozdannye apply_self)

Features:
  • Derzhit ESTER_STATE_DIR na samoy fleshke (ESTER/state), esli PORTABLE_STATE_ON_USB=1.
  • Registriruet obychnye blyuprinty (cherez register_all_routes), vklyuchaya /admin/portable.
  • Nikakikh systemd/sluzhb - prosto Flask (debug vyklyuchen).

Mosty:
- Yavnyy (Postavka ↔ Ekspluatatsiya): rabotaet “sam iz sebya” na USB.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): yavnye ENV i korni — predskazuemaya sreda.
- Skrytyy 2 (Praktika ↔ Sovmestimost): chistyy Flask+stdlib, offlayn.

Zemnoy abzats:
This is “perenosnoy pult”: votknul - zapustil - vospolzovalsya, ne kasayas ustanovlennoy systemy.

# c=a+b"""
from __future__ import annotations
import os, sys, socket
from pathlib import Path
from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Def. Portable root by file location
THIS = Path(__file__).resolve()
PORTABLE_ROOT = THIS.parents[1]

# ENV po umolchaniyu
os.environ.setdefault("PORTABLE_MODE", "1")
if os.getenv("PORTABLE_STATE_ON_USB", "1") == "1":
    os.environ["ESTER_STATE_DIR"] = str((PORTABLE_ROOT / "ESTER" / "state").resolve())
os.environ.setdefault("AB_MODE", "A")  # bezopasnyy defolt
os.environ.setdefault("PORTABLE_PORT", "5001")

def create_app() -> Flask:
    app = Flask("ester_portable")
    # Registers everything that is available
    try:
        from routes.register_all import register_all_routes  # type: ignore
        register_all_routes(app, url_prefix=None)
    except Exception:
        pass
    # Garantiruem nalichie paneli portable
    try:
        from routes.admin_portable import register_admin_portable  # type: ignore
        register_admin_portable(app, url_prefix=None)
    except Exception:
        pass

    @app.get("/")
    def root():
        host = socket.gethostname()
        return f"Ester Portable OK (host: {host}) — sm. /admin/portable"

    return app

def main():
    app = create_app()
    port = int(os.getenv("PORTABLE_PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    main()
# c=a+b