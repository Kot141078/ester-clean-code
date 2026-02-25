# -*- coding: utf-8 -*-
"""serve_no_reload.py - zapusk web-prilozheniya bez autoreload (Windows/Linux), bezopasno i predskazuemo.

Zachem:
- autoreload udoben v deve, no v “zhivoy” srede (i pod planirovschikami/sluzhbami) on often sozdaet
  dvoynye protsessy, dubliruet fonovye tiki i lomaet blokirovki/porty.

Mosty:
- Yavnyy (Kibernetika ↔ Operatsii): odin protsess = odin regulyator, bez “samoklonov”.
- Skrytyy 1 (Logika ↔ Nadezhnost): esli net tela bloka if — eto ne “oshibka stilya”, eto formalnaya
  nekorrektnost programmy (Enderton).
- Skrytyy 2 (Infoteoriya ↔ Inzheneriya): autoreload uvelichivaet noise (lishnie restarty/konnekty),
  ukhudshaya signal v logakh i metrikakh.

Zemnoy abzats:
Eto kak rubilnik v schite: v prode ty ne khochesh, chtoby “samo vklyuchalos i samo vyklyuchalos” ot
kakoy-to melkoy vibratsii. Odin protsess bez autoreload - menshe drozhaniya sistemy i menshe
povodov lovit fantomnye bagi.

# c=a+b"""

from __future__ import annotations

import os
import sys
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name, default)
    return (v or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except Exception:
        return default


def _run_flask(app: Any, host: str, port: int) -> int:
    # Flask/Werkzeug: use_reloader=False ensures that there is no second process.
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, use_reloader=False)
    return 0


def _run_asgi(app: Any, host: str, port: int) -> int:
    # ASGI (FastAPI/Starlette): reload=False
    import uvicorn  # lazy import

    log_level = _env_str("UVICORN_LOG_LEVEL", "info").lower()
    uvicorn.run(app, host=host, port=port, reload=False, log_level=log_level)
    return 0


def main() -> int:
    try:
        from wsgi_secure import app  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"[serve_no_reload] import failed: {e.__class__.__name__}: {e}", file=sys.stderr)
        return 1

    host = _env_str("ESTER_HTTP_HOST", _env_str("HOST", "127.0.0.1"))
    port = _env_int("ESTER_HTTP_PORT", _env_int("PORT", 8010))

    # Avto-detekt: Flask/Werkzeug obychno imeet .run()
    if hasattr(app, "run") and callable(getattr(app, "run")):
        return _run_flask(app, host, port)

    # Otherwise, we assume that this is an ASGI application
    return _run_asgi(app, host, port)


if __name__ == "__main__":
    raise SystemExit(main())