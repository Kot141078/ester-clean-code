# -*- coding: utf-8 -*-
"""admin_compat.py - UI/API proverok sovmestimosti s dampom (ENV/routy) v odnom fayle.

Route:
  • GET /admin/compat - stranitsa (prostaya zaglushka, chtoby ne padat bez shablona)
  • GET /admin/compat/status - bystryy otchet po USB-manifestu (esli est)
  • POST /admin/compat/scan — {manifest_text?} v†' polnyy otchet (env + routes)

Mosty:
- Yavnyy (Gamp v†" Ekspluatatsiya): sveryaem ENV Re tablitsu routov s ozhidaemym manifestom - pokazyvaem, chego ne khvataet.
- Skrytyy 1 (Infoteoriya v†" Praktika): schitaem dublikaty/konflikty routov, ubiraem "ugadayku".
- Skrytyy 2 (Kibernetika v†" Arkhitektura): A/B-slot AB_MODE (A|B) dlya bezopasnykh pereklyucheniy, bez izmeneniya koda.

Zemnoy abzats (anatomiya/inzheneriya):
Eto “priemka na konveyere”: bystroe PSM-obsledovanie pered vydachey “ustroystva” polzovatelyu —
proveryaem, chto “nervy i sosudy” (ENV i tablitsa marshrutov) podsoedineny i ne perezhaty.

# c=a+b"""
from __future__ import annotations

import os
import json
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Blueprint, jsonify, render_template_string, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- A/B slot (auto-rollback-friendly flag cherez ENV) -----------------------
AB = (os.getenv("AB_MODE") or "A").strip().upper()
if AB not in {"A", "B"}:
    AB = "A"

bp = Blueprint("admin_compat", __name__)

# =============================================================================
# Falbatsk-implementation of manifest_chesk (in case of absence of modules.comp.*)
# We maintain drop-in compatibility: if there is a module, we use it.
# =============================================================================
def _fallback_load_manifest_from_usb() -> Optional[Dict[str, Any]]:
    """Ischem JSON-manifest na semnom nositele/ryadom s proektom.
    Puti po prioritetu:
      1) ENV USB_MANIFEST_PATH
      2) ./usb-manifest.json
      3) /mnt/usb/ester-manifest.json
      4) /media/usb/ester-manifest.json"""
    candidates = [
        os.getenv("USB_MANIFEST_PATH"),
        os.path.abspath("./usb-manifest.json"),
        "/mnt/usb/ester-manifest.json",
        "/media/usb/ester-manifest.json",
    ]
    for p in candidates:
        if not p:
            continue
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            # Crashes quietly: this is a “quick status”, should not break the admin panel
            continue
    return None

def _fallback_load_manifest_from_text(text: str) -> Optional[Dict[str, Any]]:
    try:
        text = (text or "").strip()
        if not text:
            return None
        return json.loads(text)
    except Exception:
        return None

def _collect_routes() -> Dict[str, Any]:
    """We collect information about routes from current_app.url_map.
    Returns a structure with duplicate Re conflicts."""
    try:
        # We import lazily so that the module remains importable outside the Flask context
        from flask import current_app  # type: ignore

        url_map = getattr(current_app, "url_map", None)
        if not url_map:
            return {"available": False, "reason": "no_app_context"}

        rules = list(url_map.iter_rules())
        items: List[Tuple[str, str, Tuple[str, ...]]] = []
        for r in rules:
            methods = tuple(sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}))
            items.append((r.endpoint, str(r.rule), methods))

        # Analitika
        by_rule = Counter([rule for _, rule, _ in items])
        duplicate_rules = sorted([r for r, c in by_rule.items() if c > 1])

        by_endpoint: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = defaultdict(list)
        for endpoint, rule, methods in items:
            by_endpoint[endpoint].append((rule, methods))

        endpoint_conflicts: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {
            ep: lst for ep, lst in by_endpoint.items() if len(lst) > 1
        }

        return {
            "available": True,
            "total": len(items),
            "rules": sorted({rule for _, rule, _ in items}),
            "duplicate_rules": duplicate_rules,
            "endpoint_conflicts": endpoint_conflicts,
        }
    except Exception as e:
        return {"available": False, "reason": f"{type(e).__name__}: {e}"}

def _required_env_keys() -> List[str]:
    """Basic ENV checklist: can be expanded without breaking the API."""
    return [
        "HOST",
        "PORT",
        "DEBUG",
        "CORS_ENABLED",
        "TZ",
        "LOG_LEVEL",
        "JWT_SECRET",
        "JWT_SECRET_KEY",
    ]

def _env_report(require: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    req = list(require) if require else _required_env_keys()
    present, missing = {}, []
    for k in req:
        v = os.getenv(k)
        if v is None or v == "":
            missing.append(k)
            present[k] = None
        else:
            present[k] = v
    return {
        "required": req,
        "present": present,
        "missing": missing,
        "ok": len(missing) == 0,
    }

def _build_report_fallback(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Universalnyy otchet (rabotaet bez vneshnikh zavisimostey).
    Esli manifest est Re v nem ukazan ozhidaemyy ENV/routy — ispolzuem,
    inache vypolnyaem bazovye proverki."""
    env_expected = None
    manifest_routes_expected = None

    if isinstance(manifest, dict):
        env_expected = manifest.get("env_required")  # optsionalno: ["HOST", ...]
        manifest_routes_expected = manifest.get("routes_expected")  # optsionalno: ["/admin", ...]

    env_part = _env_report(env_expected)

    routes_part = _collect_routes()
    if manifest_routes_expected and routes_part.get("available"):
        have_rules = set(routes_part.get("rules", []))
        need_rules = set(manifest_routes_expected)
        routes_missing = sorted(list(need_rules - have_rules))
        routes_extra = sorted(list(have_rules - need_rules))
        routes_part["expected"] = sorted(list(need_rules))
        routes_part["missing"] = routes_missing
        routes_part["extra"] = routes_extra
        routes_part["ok"] = len(routes_missing) == 0
    else:
        # If there is no expectation, we consider it ok using basic heuristics (no conflicts/duplicates)
        if routes_part.get("available"):
            dups = routes_part.get("duplicate_rules") or []
            confs = routes_part.get("endpoint_conflicts") or {}
            routes_part["ok"] = (len(dups) == 0) and (len(confs) == 0)
        else:
            routes_part["ok"] = False

    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ab": AB,
        "env": env_part,
        "routes": routes_part,
        "manifest_hint": bool(manifest),
    }

# We are trying to connect the “native” module, if there is one
try:
    from modules.compat.manifest_check import (  # type: ignore
        load_manifest_from_usb as _ext_load_manifest_from_usb,
        load_manifest_from_text as _ext_load_manifest_from_text,
        build_report as _ext_build_report,
    )

    def load_manifest_from_usb() -> Optional[Dict[str, Any]]:
        return _ext_load_manifest_from_usb()

    def load_manifest_from_text(text: str) -> Optional[Dict[str, Any]]:
        return _ext_load_manifest_from_text(text)

    def build_report(manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        # Wrapping it up in case of exceptions: the system must live
        try:
            rep = _ext_build_report(manifest)
            # We guarantee the availability of ab/ts fields
            rep = dict(rep or {})
            rep.setdefault("ab", AB)
            rep.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
            return rep
        except Exception:
            return _build_report_fallback(manifest)

except Exception:
    # No external module - works locally
    load_manifest_from_usb = _fallback_load_manifest_from_usb
    load_manifest_from_text = _fallback_load_manifest_from_text
    build_report = _build_report_fallback

# =============================================================================
# Marshruty
# =============================================================================
@bp.get("/admin/compat")
def page():
    # We want a simple built-in page so as not to require a template
    html = """<!doctype html>
    <meta charset="utf-8" />
    <title>Ester – Admin Compat</title>
    <style>
      body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;margin:24px}
      code,pre{background:#f6f8fa;border-radius:8px;padding:2px 6px}
      .pill{display:inline-block;border:1px solid #e5e7eb;border-radius:9999px;padding:2px 10px;margin-left:8px}
      .ok{color:#065f46;border-color:#a7f3d0;background:#ecfdf5}
      .bad{color:#7f1d1d;border-color:#fecaca;background:#fef2f2}
    </style>
    <h1>Admin Compat <span class="pill">{ab}</span></h1>
    <p>Proverka sovmestimosti ENV/routov. Ispolzuyte <code>GET /admin/compat/status</code> or <code>POST /admin/compat/scan</code>.</p>""".format(
        ab=AB
    )
    return render_template_string(html)

@bp.get("/admin/compat/status")
def status():
    manifest = load_manifest_from_usb()
    rep = build_report(manifest)
    return jsonify(
        {
            "ok": bool(rep and rep.get("env", {}).get("ok") and rep.get("routes", {}).get("ok")),
            "ab": AB,
            "report": rep,
            "source": "usb" if manifest else "none",
        }
    )

@bp.post("/admin/compat/scan")
def scan():
    body = request.get_json(silent=True) or {}
    text = body.get("manifest_text") or ""
    manifest = load_manifest_from_text(text) if text else load_manifest_from_usb()
    rep = build_report(manifest)
    return jsonify({"ok": True, "ab": AB, "report": rep, "source": "text" if text else "usb_or_none"})

# =============================================================================
# Registration in the application
# =============================================================================
def register_admin_compat(app, url_prefix: Optional[str] = None) -> None:
    """
    R egistriruet blueprint dvumya sposobami:
      1) Bez prefiksa v†' /admin/compat, /admin/compat/status, /admin/compat/scan
      2) S prefiksom  v†' <prefix>/admin/compat, ...
    """
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP

        pref = _BP("admin_compat_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/compat")
        def _p():
            return page()

        @pref.get("/admin/compat/status")
        def _s():
            return status()

        @pref.post("/admin/compat/scan")
        def _sc():
            return scan()

# app.register_blueprint(pref)

# c=a+b



def register(app):
    app.register_blueprint(bp)
    return app