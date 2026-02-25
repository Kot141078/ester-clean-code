# -*- coding: utf-8 -*-
"""routes/autofix_routes.py - "tikhiy shurshatel": set, LM Studio, guard-safe diskaver, GPU, apply.

New v step-8:
  • GET /autofix/llm/models - spisok modeley iz LM Studio (keshiruetsya i obnovlyaetsya).
Ostalnoe - kak v step-7: diskaver bez HTTP (obkhod 403), pravilnaya adresatsiya cherez ACTIONS_ENDPOINT.

Mosty:
  • Yavnyy: (Kibernetika ↔ Ekspluatatsiya) - nablyudaemost i upravlenie LLM.
  • Skrytye: (Infoteoriya ↔ Seti), (Anatomiya ↔ Refleksy).

Zemnoy abzats:
  Nuzhen prostoy sposob uvidet dostupnye modeli i bystro “razmyat” odnu iz nikh - vot zachem /llm/models i knopki v UI.

# c=a+b"""
from __future__ import annotations

import os
import json
import time
import glob
import socket
import threading
import logging
import importlib
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request, current_app, Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

autofix_bp = Blueprint("autofix", __name__)
bp = autofix_bp  # for discover.register

# Global link to the application (needed for a background thread if there is no registred context)
_APP: Optional[Flask] = None

_STATE: Dict[str, Any] = {
    "running": False,
    "last_ts": 0.0,
    "period_sec": int(os.getenv("AUTOFIX_PERIOD_SEC", "20") or "20"),
    "discover_last_ts": 0.0,
    "discover_min_interval_sec": int(os.getenv("AUTOFIX_DISCOVER_MIN_INTERVAL_SEC", "600") or "600"),
    "net": {"ok": None, "detail": ""},
    "lmstudio": {"ok": None, "detail": "", "models": []},
    "discover": {"ok": None, "detail": "", "registered": 0, "scanned": 0},
    "cycles": 0,
    "events": [],
}
_LOCK = threading.RLock()
_THREAD: Optional[threading.Thread] = None
_STOP = threading.Event()

def _log_info(msg: str) -> None:
    try:
        logger = current_app.logger  # type: ignore
    except Exception:
        logger = logging.getLogger("autofix")
    try:
        logger.info(msg)
    except Exception:
        pass

def _push_event(topic: str, payload: Dict[str, Any]) -> None:
    try:
        import modules as _m  # type: ignore
        if hasattr(_m, "events_bus") and _m.events_bus:
            _m.events_bus.publish(topic, dict(payload or {}))
    except Exception:
        pass
    with _LOCK:
        _STATE["events"].append({"ts": time.time(), "topic": topic, "payload": dict(payload or {})})
        _STATE["events"] = _STATE["events"][-50:]

# ---------- helpers: set / lm studio / http / gpu ----------

def _net_probe() -> Tuple[bool, str]:
    """Quick TCP test. Important: the socket is closed even with ConnectionRefused."""
    targets = [("1.1.1.1", 53), ("8.8.8.8", 53), ("127.0.0.1", 80)]
    ok_any = False
    detail = []

    for host, port in targets:
        try:
            # Important: through the manager context, the socket will be closed even if connect() fails.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect((host, port))
            ok_any = True
            detail.append(f"{host}:{port}=OK")
        except Exception as e:  # noqa: BLE001
            detail.append(f"{host}:{port}=FAIL({e.__class__.__name__})")

    return ok_any, "; ".join(detail)
def _lmstudio_base() -> str:
    return (os.getenv("LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234/v1").rstrip("/")

def _lmstudio_headers() -> Dict[str, str]:
    hdr = {"Content-Type": "application/json"}
    key = os.getenv("LMSTUDIO_API_KEY") or ""
    if key:
        hdr["Authorization"] = f"Bearer {key}"
    return hdr

def _http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Tuple[int, Any]:
    import urllib.request
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_lmstudio_headers(), method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            try:
                return r.getcode(), json.loads(raw)
            except Exception:
                return r.getcode(), raw
    except Exception as e:
        return 0, {"error": f"{e.__class__.__name__}: {e}"}

def _lmstudio_models() -> List[str]:
    code, body = _http_json("GET", f"{_lmstudio_base()}/models", None, timeout=8)
    names: List[str] = []
    if code == 200 and isinstance(body, dict):
        for it in body.get("data", []):
            name = it.get("id") or it.get("name")
            if name:
                names.append(str(name))
    with _LOCK:
        _STATE["lmstudio"]["models"] = names
    return names

def _choose_model() -> Optional[str]:
    env_model = os.getenv("LMSTUDIO_MODEL")
    if env_model:
        return env_model
    names = _STATE.get("lmstudio", {}).get("models") or []
    if not names:
        names = _lmstudio_models()
    return names[0] if names else None

def _lmstudio_chat_api(messages: List[Dict[str, str]], max_tokens: int = 256, temperature: float = 0.2) -> Tuple[bool, Dict[str, Any]]:
    model = _choose_model()
    if not model:
        return False, {"error": "no_model", "hint": "Net dostupnykh modeley v LM Studio. Otkroy LM Studio i dobav/zagruzi model."}
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False}
    code, body = _http_json("POST", f"{_lmstudio_base()}/chat/completions", payload, timeout=60)
    return (code == 200), {"code": code, "body": body, "model": model}

def _local_url(path: str) -> str:
    base = os.getenv("ACTIONS_ENDPOINT")
    if base:
        base = base.rstrip("/")
        p = path if path.startswith("/") else "/" + path
        return base + p
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000") or "8000")
    p = path if path.startswith("/") else "/" + path
    return f"http://{host}:{port}{p}"

def _gpu_metrics() -> Dict[str, Any]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.STDOUT, timeout=3, shell=False, creationflags=0
        ).decode("utf-8", errors="ignore").strip()
        rows = []
        for line in out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                rows.append({"util": int(parts[0]), "mem_used": int(parts[1]), "mem_total": int(parts[2])})
        return {"ok": True, "gpus": rows}
    except Exception as e:
        return {"ok": False, "error": str(e), "hint": "nvidia-smi nedostupen ili ne v PATH"}

# ---------- guard-safe DISCOVER (bez HTTP) ----------

def _scan_route_modules() -> List[str]:
    mods = []
    for path in glob.glob(os.path.join(os.getcwd(), "routes", "*_routes.py")):
        mods.append("routes." + os.path.splitext(os.path.basename(path))[0])
    return sorted(set(mods))

def _safe_direct_register(app: Flask, dotted: str) -> Dict[str, Any]:
    try:
        mod = importlib.import_module(dotted)
    except Exception as e:
        return {"module": dotted, "ok": False, "error": f"import: {e}"}
    try:
        if hasattr(mod, "register") and callable(getattr(mod, "register")):
            mod.register(app);  return {"module": dotted, "ok": True, "via": "register(app)"}
        if hasattr(mod, "bp"):
            app.register_blueprint(getattr(mod, "bp"));  return {"module": dotted, "ok": True, "via": "bp"}
        return {"module": dotted, "ok": False, "error": "no register() or bp"}
    except Exception as e:
        return {"module": dotted, "ok": False, "error": f"mount: {e}"}

def _discover_scan() -> Tuple[bool, str, int, int]:
    ok = True; reg_ok = 0; scanned = 0; details: List[str] = []

    app = _APP
    if app is None:
        try:
            app = current_app._get_current_object()  # type: ignore
        except Exception:
            app = None

    if app is not None:
        ctx = app.app_context()
        try:
            ctx.push()
            mods = _scan_route_modules()
            scanned = len(mods)
            for m in mods:
                r = _safe_direct_register(app, m)
                if r.get("ok"): reg_ok += 1
            details.append(f"direct:{reg_ok}/{scanned}")
        finally:
            try: ctx.pop()
            except Exception: pass
    else:
        ok = False
        details.append("direct:app_missing")

    # HTTP (best-effort, maybe 403 is not an error)
    code_scan, _ = _http_json("GET", _local_url("/app/discover/scan"), None, timeout=4)
    code_rl, _   = _http_json("POST", _local_url("/debug/actions/reload"), {}, timeout=4)
    details.append(f"http:scan={code_scan},reload={code_rl}")

    ok = ok and (reg_ok > 0)
    return ok, "; ".join(details), reg_ok, scanned

# ---------- tsikl / servis ----------

def _cycle_once() -> None:
    net_ok, net_detail = _net_probe()
    with _LOCK:
        _STATE["net"] = {"ok": net_ok, "detail": net_detail}

    names = _lmstudio_models()
    llm_ok = len(names) > 0
    with _LOCK:
        _STATE["lmstudio"]["ok"] = llm_ok
        _STATE["lmstudio"]["detail"] = f"models={len(names)} @ {_lmstudio_base()}"

    with _LOCK:
        disc_interval = max(5, int(_STATE.get("discover_min_interval_sec") or 600))
        last_disc_ts = float(_STATE.get("discover_last_ts") or 0.0)
        prev_disc = dict(_STATE.get("discover") or {})
    due_discover = (time.time() - last_disc_ts) >= disc_interval
    run_discover = bool(due_discover or (prev_disc.get("ok") in (None, False)))

    if run_discover:
        disc_ok, disc_detail, reg_count, scanned = _discover_scan()
        with _LOCK:
            _STATE["discover"] = {"ok": disc_ok, "detail": disc_detail, "registered": reg_count, "scanned": scanned}
            _STATE["discover_last_ts"] = time.time()
    else:
        disc_ok = bool(prev_disc.get("ok", True))
        disc_detail = f"skipped(interval={disc_interval}s)"

    _log_info(f"autofix: cycle net={int(net_ok)} lm={int(llm_ok)} disc={int(disc_ok)} models={len(names)}")
    _push_event("autofix.cycle", {"net_ok": net_ok, "lm_ok": llm_ok, "disc_ok": disc_ok, "models": names, "disc_detail": disc_detail})

def _worker() -> None:
    period = max(5, int(_STATE.get("period_sec") or 20))
    while not _STOP.is_set():
        try:
            _cycle_once()
            with _LOCK:
                _STATE["cycles"] = int(_STATE.get("cycles", 0)) + 1
                _STATE["last_ts"] = time.time()
        except Exception as e:
            _log_info(f"autofix: error {e.__class__.__name__}: {e}")
            _push_event("autofix.error", {"error": f"{e.__class__.__name__}: {e}"})
        _STOP.wait(period)

def _ensure_started() -> bool:
    global _THREAD
    with _LOCK:
        if _STATE["running"]: return True
        _STATE["running"] = True
    _STOP.clear()
    t = threading.Thread(target=_worker, name="Ester-Autofix", daemon=True); t.start()
    _THREAD = t
    _log_info(f"autofix: started period={_STATE['period_sec']}s base={_lmstudio_base()}")
    _push_event("autofix.started", {"period_sec": _STATE["period_sec"]})
    return True

# ---------- endpoints ----------

@autofix_bp.route("/autofix/status", methods=["GET"])
def autofix_status():
    with _LOCK: out = dict(_STATE)
    out["gpu"] = _gpu_metrics()
    return jsonify({"ok": True, "state": out})

@autofix_bp.route("/autofix/start", methods=["POST"])
def autofix_start():
    return jsonify({"ok": bool(_ensure_started()), "running": True})

@autofix_bp.route("/autofix/ping", methods=["POST"])
def autofix_ping():
    _cycle_once()
    with _LOCK: out = dict(_STATE)
    out["gpu"] = _gpu_metrics()
    return jsonify({"ok": True, "state": out})

@autofix_bp.route("/autofix/gpu", methods=["GET"])
def autofix_gpu():
    return jsonify(_gpu_metrics())

@autofix_bp.route("/autofix/llm/status", methods=["GET"])
def autofix_llm_status():
    with _LOCK: llm = dict(_STATE.get("lmstudio", {}))
    return jsonify({"ok": True, "lmstudio": llm, "base": _lmstudio_base(), "model": _choose_model()})

@autofix_bp.route("/autofix/llm/models", methods=["GET"])
def autofix_llm_models():
    models = _STATE.get("lmstudio", {}).get("models") or _lmstudio_models()
    return jsonify({"ok": True, "models": models})

@autofix_bp.route("/autofix/llm/warmup", methods=["POST","GET"])
def autofix_llm_warmup():
    ok, res = _lmstudio_chat_api([{"role":"user","content":"Say 'READY' and stop."}], max_tokens=48, temperature=0.0)
    return jsonify({"ok": bool(ok), "result": res})

@autofix_bp.route("/autofix/llm/chat", methods=["POST"])
def autofix_llm_chat():
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt", "Hello from Ester. Respond briefly."))
    max_tokens = int(data.get("max_tokens", 128) or 128)
    temp = float(data.get("temperature", 0.2) or 0.2)
    ok, res = _lmstudio_chat_api([{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=temp)
    return jsonify({"ok": bool(ok), "result": res})

@autofix_bp.route("/autofix/discover", methods=["POST"])
def autofix_discover():
    ok, detail, reg, scanned = _discover_scan()
    return jsonify({"ok": ok, "detail": detail, "registered": reg, "scanned": scanned})

@autofix_bp.route("/autofix/apply", methods=["POST"])
def autofix_apply():
    mode = (os.getenv("AUTOFIX_APPLY_MODE", "A") or "A").upper()
    data = request.get_json(silent=True) or {}
    action = str(data.get("action","")).strip()

    if mode == "B":
        return jsonify({"ok": True, "dry_run": True, "action": action})

    if action == "set_env":
        kv = dict(data.get("kv") or {})
        for k,v in kv.items(): os.environ[str(k)] = str(v)
        if any(k in kv for k in ("LMSTUDIO_BASE_URL","LMSTUDIO_API_KEY")): _lmstudio_models()
        return jsonify({"ok": True, "applied": list(kv.keys())})

    if action == "discover.force":
        ok, detail, reg, scanned = _discover_scan()
        return jsonify({"ok": ok, "detail": detail, "registered": reg, "scanned": scanned})

    if action == "lm.warmup":
        ok, res = _lmstudio_chat_api([{"role":"user","content":"Warmup. Reply: OK."}], max_tokens=96, temperature=0.0)
        return jsonify({"ok": bool(ok), "result": res})

    if action == "pip.hints":
        hints=[{"import":"openai","pip":"pip install openai>=1.40"},{"import":"google-generativeai","pip":"pip install google-generativeai>=0.7"},{"import":"googleapiclient.discovery","pip":"pip install google-api-python-client>=2.130"},{"import":"cryptography","pip":"pip install cryptography>=42"},{"import":"python-telegram-bot","pip":"pip install python-telegram-bot>=21,<23"}]
        return jsonify({"ok": True, "hints": hints})

    return jsonify({"ok": False, "error": "unknown_action"})

def register(app: Flask) -> None:
    global _APP
    _APP = app
    app.register_blueprint(bp)
    _maybe_autostart()

def _maybe_autostart() -> None:
    en = str(os.getenv("AUTOFIX_ENABLED", "1")).strip().lower()
    if en in ("1","true","yes","on"):
        try: _ensure_started()
        except Exception: pass

@autofix_bp.record_once
def _on_register(setup_state):
    _maybe_autostart()
# c=a+b


def register(app):
    app.register_blueprint(autofix_bp)
    return app
