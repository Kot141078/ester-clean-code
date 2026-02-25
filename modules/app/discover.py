# -*- coding: utf-8 -*-
"""modules/app/discover.py - obedinennyy scanner/reestr/registrator moduley/routov.

Mosty:
- Yavnyy: (Prilozhenie ↔ Rasshiryaemost/Samorazvitie) nakhodit i podklyuchaet novye routy bez pravki app.py.
- Skrytyy #1: (Audit/RBAC ↔ Bezopasnost) vedet reestr s sha256/ts/origin, A/B-test, allowed prefixes.
- Skrytyy #2: (Kibernetika ↔ Samosborka) osnova dlya avto-registratsii, parsing bez importa + Blueprint.
- Skrytyy #3: (Trust ↔ Integritet) audit-log deystviy.

Zemnoy abzats:
This is “USB-port + profilenyy kontrol” dlya koda: nashel modul (routes.*_routes.py or extra), proveril otpechatok, akkuratno primontiroval k Flask. Ne teryaem kontekst - pomnim vse!

# c=a+b"""
from __future__ import annotations
import importlib, importlib.util, json, os, pkgutil, sys, time, hashlib
from typing import Any, Dict, List
from flask import Flask  # for type-hint, assiming Flask app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("APP_DISCOVER_AB", "A") or "A").upper()
REG_PATH = os.getenv("APP_DISCOVER_REG", "data/app/discover.json")
EXTRA_PATH = os.getenv("APP_DISCOVER_EXTRA", "data/app/extra_routes.json")
ALLOWED = tuple([p.strip() for p in (os.getenv("DISCOVER_ALLOWED_PKGS", "routes.,modules.") or "").split(",") if p.strip()])
AUDIT_LOG = os.getenv("DISCOVER_AUDIT_LOG", "data/app/discover_audit.log")
FILTER_ROUTES_SUFFIX = bool(int(os.getenv("DISCOVER_FILTER_ROUTES", "1")))  # 1=filtr na _routes.py
AUTO_REGISTER = bool(int(os.getenv("DISCOVER_AUTO", "0")))  # 0=off, 1=auto when pissing if missing

def _ensure():
    os.makedirs(os.path.dirname(REG_PATH), exist_ok=True)
    if not os.path.isfile(REG_PATH):
        json.dump({"modules": {}, "registered": []}, open(REG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not os.path.isfile(EXTRA_PATH):
        json.dump({"modules": []}, open(EXTRA_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)  # for log

def _load() -> Dict[str, Any]:
    _ensure()
    return json.load(open(REG_PATH, "r", encoding="utf-8"))

def _save(j: Dict[str, Any]):
    json.dump(j, open(REG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _log_audit(msg: str):
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def _extra_modules() -> List[str]:
    try:
        return [m.strip() for m in json.load(open(EXTRA_PATH, "r", encoding="utf-8")).get("modules", []) if m.strip()]
    except Exception:
        _log_audit("Warning: Failed to load extra_modules")
        return []

def _module_origin(mod_name: str) -> str:
    try:
        spec = importlib.util.find_spec(mod_name)
        if spec and spec.origin:
            return os.path.abspath(spec.origin)
    except Exception:
        pass
    p = mod_name.replace(".", os.sep) + ".py"
    if os.path.exists(p):
        return os.path.abspath(p)
    return ""

def _sha256_file(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        _log_audit(f"Warning: Failed to compute sha256 for {path}")
        return ""

def _has_register_via_parse(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return "def register(app):" in text
    except Exception:
        return False

def scan() -> Dict[str, Any]:
    """Searches for modules in Allowed prefixes, with the _rutes.po filter (if enabled), plus extra. Returns fund, registered, messing."""
    found = set()
    # 1) Via pkgutil for packages
    for prefix in [p.rstrip(".") for p in ALLOWED if p]:
        if not os.path.isdir(prefix):
            continue
        try:
            pkg = importlib.import_module(prefix)
            for it in pkgutil.iter_modules(pkg.__path__, prefix + "."):
                if it.ispkg:
                    continue
                if FILTER_ROUTES_SUFFIX and not it.name.endswith("_routes"):
                    continue
                found.add(it.name)
        except Exception:
            # 2) Fallback po faylovoy sisteme
            for fn in os.listdir(prefix):
                if fn.endswith(".py") and not fn.startswith("__"):
                    mod_name = f"{prefix}.{fn[:-3]}"
                    if FILTER_ROUTES_SUFFIX and not fn.endswith("_routes.py"):
                        continue
                    found.add(mod_name)
    # 3) Dobavit extra
    for m in _extra_modules():
        if m:
            found.add(m)
    # 4) Allowed filter and presence of a register (parse without import for security)
    candidates = []
    for name in sorted(found):
        if not any(name.startswith(p) for p in ALLOWED):
            continue
        path = _module_origin(name)
        if not _has_register_via_parse(path):
            continue  # Only with register for compatibility
        sha = _sha256_file(path)
        candidates.append({"module": name, "path": path, "sha256": sha})
    # Sravnenie s reestrom
    reg = _load()
    registered = set(reg.get("registered", []) + list(reg.get("modules", {}).keys()))
    missing = [c["module"] for c in candidates if c["module"] not in registered]
    _log_audit(f"Scan: found {len(candidates)}, registered {len(registered)}, missing {len(missing)}")
    return {
        "ok": True,
        "found": [c["module"] for c in candidates],
        "registered": sorted(list(registered)),
        "missing": sorted(missing),
        "items": candidates,
        "ab": AB
    }

def status() -> Dict[str, Any]:
    return {"ok": True, **_load()}

def register_modules(modules: List[str], app: Flask) -> Dict[str, Any]:
    """Registers modules: allowed check, import, register or bp, entry to the register from sha/ts/origin.
    If AB=="B", report only."""
    if AB == "B":
        _log_audit("Register attempt blocked: AB=B")
        return {"ok": False, "error": "APP_DISCOVER_AB=B"}
    reg = _load()
    modules_dict = reg.get("modules", {})
    registered_list = reg.get("registered", [])
    results = []
    ok_all = True
    for mod_name in modules or []:
        rec = {"module": mod_name, "ok": False}
        if not any(mod_name.startswith(p) for p in ALLOWED):
            rec["error"] = "not_allowed"
            results.append(rec)
            ok_all = False
            continue
        try:
            mod = importlib.import_module(mod_name)
            origin = _module_origin(mod_name)
            sha = _sha256_file(origin)
            # 1) register(app)
            if hasattr(mod, "register") and callable(mod.register):
                mod.register(app)
                rec["via"] = "register"
            # 2) Blueprint bp
            elif hasattr(mod, "bp"):
                app.register_blueprint(mod.bp)
                rec["via"] = "bp"
            else:
                rec["error"] = "no_register_or_bp"
                ok_all = False
                results.append(rec)
                continue
            # Success: entry into the registry
            modules_dict[mod_name] = {"ts": int(time.time()), "origin": origin, "sha256": sha}
            if mod_name not in registered_list:
                registered_list.append(mod_name)
            rec["ok"] = True
            rec["sha256"] = sha
            rec["origin"] = origin
            _log_audit(f"Registered {mod_name} via {rec['via']}, sha={sha}")
        except Exception as e:
            rec["error"] = f"{e.__class__.__name__}: {e}"
            ok_all = False
            _log_audit(f"Error registering {mod_name}: {rec['error']}")
        results.append(rec)
    reg["modules"] = modules_dict
    reg["registered"] = sorted(registered_list)
    _save(reg)
    return {"ok": ok_all, "results": results, "registered_now": [r["module"] for r in results if r["ok"]], "all_registered": reg["registered"]}

# Optional auto-registration (extension)
if AUTO_REGISTER:
    from flask import Flask  # assuming we can import app here, else adjust
    app = Flask(__name__)  # Placeholder; replace with real app import
    s = scan()
    if s["missing"]:
        register_modules(s["missing"], app)
