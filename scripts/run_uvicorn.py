# -*- coding: utf-8 -*-
"""scripts/run_uvicorn.py - edinyy oflayn-launcher dlya interfeysa Ester.

MOSTY:
- (Yavnyy) Zapuskaet asgi/app_main:app (FastAPI + WSGI/Flask) bez pravok suschestvuyuschikh faylov.
- (Skrytyy #1) Uchityvaet HOST/PORT/DEBUG iz ENV i myagko podstavlyaet znacheniya iz dampa.
- (Skrytyy #2) A/B-slot ESTER_AB_INTERFACE: A - myagko, B - strictly (add. proverki i zagolovki).

ZEMNOY ABZATs:
This is “PUSK button” dlya web-interfeysa. Odin fayl - odin protsess uvicorn, kotoryy obsluzhivaet i API, i bordy.
Rabotaet oflayn, ne menyaet kontrakty HTTP/JSON i puti shablonov.

c=a+b"""
from __future__ import annotations
import os, sys, logging
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if (v is not None and str(v).strip() != "") else default

def main():
    # Launch options (drop-in compatible with dump)
    host = _env("HOST", _env("ESTER_HOST", "127.0.0.1"))
    port = int(_env("PORT", _env("ESTER_PORT", "8010")))
    log_level = "debug" if _env("DEBUG", _env("FLASK_DEBUG", "0")) in {"1","true","True"} else "info"
    ab = (_env("ESTER_AB_INTERFACE", "A") or "A").upper()

    # Import lokalnogo prilozheniya (asgi/app_main:app)
    try:
        from asgi.app_main import app as asgi_app  # type: ignore
    except Exception as e:
        print(f"y!sch Failed to import asgi.app_mine: ZZF0Z", file=sys.stderr)
        sys.exit(2)

    # Add. B-mode boosts without breaking contracts
    if ab == "B":
        try:
            # Secure headers (if module is present)
            from asgi.security_headers import add_security_headers  # type: ignore
            add_security_headers(asgi_app)
        except Exception:
            pass

    # Launching Uvicorn (locally, without the Internet)
    try:
        import uvicorn  # type: ignore
    except Exception as e:
        print("[!] Modul uvicorn ne ustanovlen. Ustanovite zavisimosti iz requirements/interface_min.txt", file=sys.stderr)
        raise

    # Vyvodim ponyatnyy log
    logging.getLogger("uvicorn").setLevel(logging.INFO if log_level=="info" else logging.DEBUG)
    print(f"Ester ASGI: {host}:{port} (AB={ab}, log={log_level})")
    uvicorn.run(asgi_app, host=host, port=port, log_level=log_level)

if __name__ == "__main__":
    main()