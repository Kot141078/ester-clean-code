# -*- coding: utf-8 -*-
"""
modules/thinking/actions_discovery.py — discover.* + debug/doctor + bootstrap.

Zachem etot fayl:
- Avtozagruzka "neyronov" iz modules/thinking po prefiksam (actions_/cascade_/loop_/volition_/affect_).
- Registratsiya discover.* deystviy v action_registry c timeout_sec i concurrency.
- Optsionalno: dobavlyaet /debug/actions i /debug/doctor (esli peredan Flask app).

Fiksy/usileniya (po sravneniyu s chasto vstrechayuschimisya polomannymi versiyami):
- Net BOM/markdown-obvyazki → ne byvaet SyntaxError na stroke 2.
- Put dlya skanirovaniya beretsya ot __file__ (ne zavisit ot cwd).
- Myagkiy sys.path fallback: esli fayl gruzyat kak odinochku, absolute-import modules.* ne lomaetsya.

Mosty:
- Yavnyy most: action_registry.register → HTTP-routy discover.* (edinyy kontrakt deystviya).
- Skrytye mosty:
  1) Infoteoriya ↔ ustoychivost: timeout_sec + concurrency = ogranichenie propusknoy sposobnosti (ne daem sisteme “zakhlebnutsya”).
  2) Inzheneriya ↔ ekspluatatsiya: avtoskan po __file__ = menshe “magii” v zapuske.

ZEMNOY ABZATs: v kontse fayla.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- sys.path fallback (kogda modul gruzyat kak fayl) ---
import sys as _sys
if __package__ in (None, ""):  # pragma: no cover
    try:
        _here = Path(__file__).resolve()
        _root = _here.parents[2]  # <root>/modules/thinking/actions_discovery.py
        if str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
    except Exception:
        pass

# Importiruem tsentralnyy reestr zdorovya (optsionalno)
try:
    from modules.health_check import HealthCheck  # type: ignore
except Exception:
    HealthCheck = None  # type: ignore

from modules.thinking.action_registry import (  # type: ignore
    register as _areg,
    list_registered as _alist,
    set_endpoint as _set_ep,
)
from modules.memory.facade import memory_add

log = logging.getLogger(__name__)

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

# -------------------------
# env helpers
# -------------------------
def _base_url() -> str:
    """Opredelyaet adres API Ester."""
    ep = (os.getenv("ACTIONS_ENDPOINT") or "").strip().strip('"')
    if ep:
        return ep.rstrip("/")

    api = (os.getenv("ESTER_API_BASE") or "").strip().strip('"')
    if api:
        return api.rstrip("/")

    port = int(os.getenv("PORT", "8000") or "8000")
    return f"http://127.0.0.1:{port}"


_DEFAULT_HTTP_TIMEOUT = int(os.getenv("ACTIONS_DEFAULT_TIMEOUT_SEC", "8") or "8")
_AUTOFIX_ENABLED = str(os.getenv("AUTOFIX_ENABLED", "1")).lower() in ("1", "true", "yes")
_AUTOFIX_BOOTSTRAP = str(os.getenv("AUTOFIX_BOOTSTRAP", "1")).lower() in ("1", "true", "yes")
_BOOT_LOCK = threading.RLock()
_BOOT_STARTED = False

# -------------------------
# HTTP utils
# -------------------------
def _http_json(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Tuple[int, Any]:
    url = _base_url() + (path if path.startswith("/") else "/" + path)
    t = int(timeout if timeout is not None else _DEFAULT_HTTP_TIMEOUT)

    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=t) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            try:
                return int(r.getcode()), json.loads(raw)
            except Exception:
                return int(r.getcode()), raw
    except urllib.error.HTTPError as e:
        return int(e.code), {"error": f"HTTPError {e.code}"}
    except Exception as e:
        return 0, {"error": f"{e.__class__.__name__}: {e}"}

# -------------------------
# Hive Mind: Auto-Loader
# -------------------------
def _force_scan_thinking_modules() -> None:
    """Skaniruet papku modules/thinking i aktiviruet navyki."""
    base_path = Path(__file__).resolve().parent  # .../modules/thinking
    if not base_path.exists():
        return

    try:
        log.info("[Discovery] scan thinking: %s", str(base_path))
    except Exception:
        pass

    count = 0
    for file_path in base_path.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        name = file_path.name
        if (
            name.startswith("actions_")
            or name.startswith("cascade_")
            or name.startswith("loop_")
            or name.startswith("volition_")
            or name.startswith("affect_")
        ):
            module_name = f"modules.thinking.{file_path.stem}"
            try:
                importlib.import_module(module_name)
                count += 1
            except Exception as e:
                try:
                    log.error("[Discovery] failed to import %s: %s", module_name, e)
                except Exception:
                    pass
                try:
                    _mirror_background_event(
                        f"[DISCOVERY_IMPORT_FAIL] {module_name} err={e}",
                        "actions_discovery",
                        "import_fail",
                    )
                except Exception:
                    pass

    try:
        log.info("[Discovery] activated=%d", count)
    except Exception:
        pass
    try:
        _mirror_background_event(
            f"[DISCOVERY_SCAN_DONE] activated={count}",
            "actions_discovery",
            "scan_done",
        )
    except Exception:
        pass

# -------------------------
# Debug Routes
# -------------------------
def _collect_imports_via_healthcheck() -> Dict[str, Any]:
    if not HealthCheck:
        return {"ok": 0, "fail": 1, "items": [{"name": "HealthCheck", "ok": False}]}

    hc = HealthCheck()  # type: ignore
    try:
        results = hc.run_all_checks()
    except Exception as e:
        return {"ok": 0, "fail": 1, "items": [{"name": "Diagnostics", "ok": False, "detail": str(e)}]}

    items: List[Dict[str, Any]] = []
    ok_count = 0
    fail_count = 0
    for mod_name, status in (results or {}).items():
        is_ok = status is True or (isinstance(status, str) and "OK" in status)
        if is_ok:
            ok_count += 1
        else:
            fail_count += 1
        items.append({"name": str(mod_name), "ok": bool(is_ok), "detail": str(status)})

    return {"ok": ok_count, "fail": fail_count, "items": items}

def _ensure_debug_routes(app: Any) -> None:
    existing_rules = set()
    try:
        existing_rules = {str(r.rule) for r in app.url_map.iter_rules()}
    except Exception:
        pass

    if "/debug/actions" not in existing_rules:
        @app.route("/debug/actions", methods=["GET"])
        def _debug_actions():  # type: ignore
            if not _alist():
                _force_scan_thinking_modules()
            try:
                return json.dumps({"ok": True, "actions": _alist()}, ensure_ascii=False), 200, {"Content-Type": "application/json"}
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 500, {"Content-Type": "application/json"}

    if "/debug/doctor" not in existing_rules:
        @app.route("/debug/doctor", methods=["GET"])
        def _debug_doctor():  # type: ignore
            try:
                imps = _collect_imports_via_healthcheck()
                rep = {
                    "ok": imps.get("fail", 0) == 0,
                    "env": {"HOST": "127.0.0.1"},
                    "system_health": imps,
                }
                return json.dumps(rep, ensure_ascii=False), 200, {"Content-Type": "application/json"}
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 500, {"Content-Type": "application/json"}

# -------------------------
# Main Discovery
# -------------------------
def discover_actions(app: Optional[Any] = None, *, bootstrap: bool = True) -> Dict[str, Dict[str, Any]]:
    """Registriruet discover.* i vozvraschaet kartu zaregistrirovannykh deystviy."""
    try:
        _set_ep(_base_url())
    except Exception:
        pass

    # 1) avto-zagruzka moduley myshleniya
    _force_scan_thinking_modules()

    # 2) debug routes (po zhelaniyu)
    if app is not None:
        try:
            mod = importlib.import_module("routes.autofix_routes")
            if hasattr(mod, "register"):
                mod.register(app)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            _ensure_debug_routes(app)
        except Exception:
            pass

    # 3) registratsiya deystviy s timeout/concurrency
    _areg(
        kind="discover.scan",
        inputs={},
        outputs={"ok": "bool"},
        timeout_sec=15,
        concurrency=1,
        fn=lambda a: _http_json("GET", "/app/discover/scan", None, timeout=15)[1],
    )
    _areg(
        kind="discover.status",
        inputs={},
        outputs={"ok": "bool"},
        timeout_sec=10,
        concurrency=2,
        fn=lambda a: _http_json("GET", "/app/discover/status", None, timeout=10)[1],
    )
    _areg(
        kind="discover.register",
        inputs={"modules": "list"},
        outputs={"ok": "bool"},
        timeout_sec=60,
        concurrency=1,
        fn=lambda a: _http_json(
            "POST",
            "/app/discover/register",
            {"modules": list(a.get("modules") or [])},
            timeout=60,
        )[1],
    )

    # 4) bootstrap (one-shot, no recursive reload)
    if bootstrap and _AUTOFIX_ENABLED and _AUTOFIX_BOOTSTRAP:
        def _boot() -> None:
            time.sleep(2.0)
            code, _ = _http_json("GET", "/debug/doctor", None, timeout=4)
            try:
                _mirror_background_event(
                    f"[DISCOVERY_BOOTSTRAP_DONE] doctor_code={code}",
                    "actions_discovery",
                    "bootstrap",
                )
            except Exception:
                pass

        global _BOOT_STARTED
        with _BOOT_LOCK:
            if not _BOOT_STARTED:
                _BOOT_STARTED = True
                try:
                    threading.Thread(target=_boot, name="Ester-Autofix-Boot", daemon=True).start()
                except Exception:
                    _BOOT_STARTED = False

    return _alist()


__all__ = ["discover_actions"]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Discovery — eto kak “zritelnaya kora” u operatora: bystro zametit, chto poyavilos novoe.
No esli glaza morgayut beskonechno bystro — mozg zavisaet. Poetomu timeout_sec i concurrency — eto
kak chastota i ogranichenie nagruzki: vidim dostatochno, chtoby deystvovat, no ne ukhodim v sudorogi.
"""
