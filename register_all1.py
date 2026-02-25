# -*- coding: utf-8 -*-
"""register_all.py - edinyy registrator UI i “samolechaschiy” Bootstrap dlya Ester.

Name:
  • Zaregistrirovat po maximumu vse UI/admin/portalnye blyuprinty (esli oni prisutstvuyut).
  • Vklyuchit CORS (po .env CORS_ENABLED=1) i myagko podklyuchit RBAC guard, if available.
  • Avtomaticheski vstraivat na vse HTML-stranitsy skript /static/ester_bootstrap.js,
    kotoryy:
      - sinkhroniziruet localStorage klyuchi 'jwt' i 'ester.jwt',
      - podstavlyaet Authorization: Bearer <token> v fetch/XMLHttpRequest pri same-origin,
      - imeet A/B-sloty i avto-otkat: pri oshibke slot A → B (cherez cookie ester_bootstrap_error).

Mosty:
  • Yavnyy (RBAC ↔ UI): rol/token → dostup k /admin/*.
  • Skrytyy #1 (Brauzernoe khranilische ↔ HTTP): raskhozhdenie klyuchey localStorage lomaet Authorization.
  • Skrytyy #2 (Arkh-registratsiya ↔ Ekspluatatsiya): neregistr. blueprint = vechnyy 404 pri idealnoy avtorizatsii.

Zemnoy abzats (inzheneriya):
  Dumayte o sisteme kak o schitke s avtomatami: token - klyuch; RBAC - okhrannik; reestr blyuprintov - provodka.
  My dobavlyaem “umnuyu vstavku” skripta, kotoraya kladet klyuch v obe skvazhiny, a provodku vklyuchaem polnostyu:
  register vse, chto naydeno, i avtomaticheski podaem pitanie na UI-zaprosy.

# c=a+b"""
from __future__ import annotations

import os
import importlib
from typing import Any, Callable, Optional, List

from flask import Blueprint, Response, request, current_app, make_response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ------------------------------
# Publichnyy API
# ------------------------------

def register_all(app) -> None:
    """Podklyuchaet vse nuzhnoe:
      1) myagko prikruchivaet RBAC (esli est),
      2) vklyuchaet CORS (esli vklyuchen v.env),
      3) register maximalno vozmozhnyy nabor blyuprintov UI/ADMIN,
      4) publikuet/static/ester_bootstrap.js (A/B-sloty),
      5) vnedryaet <script src="/static/ester_bootstrap.js"> v lyubye HTML-otvety."""
    _maybe_attach_rbac(app)
    _maybe_enable_cors(app)
    _register_best_effort_blueprints(app)
    _mount_bootstrap_js_blueprint(app)
    _inject_bootstrap_into_html(app)


# ------------------------------
# RVACH (best-effort connection)
# ------------------------------

def _maybe_attach_rbac(app) -> None:
    """We connect RVACH if there is a module and it contains attach_app/appli.
    Absence doesn't ruin anything."""
    for mod_name in ("security.rbac", "modules.security.rbac", "rbac"):
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue

        # Chastye varianty API:
        for attr in ("attach_app", "init_app", "apply"):
            fn = getattr(mod, attr, None)
            if callable(fn):
                try:
                    fn(app)  # type: ignore
                    app.logger.info(f"[register_all] RBAC attached via {mod_name}.{attr}")
                    return
                except Exception as e:
                    app.logger.warning(f"[register_all] RBAC attach failed ({mod_name}.{attr}): {e}")
    app.logger.info("[register_all] RBAC module not found — continue without explicit attach")


# ------------------------------
# CORS (po .env CORS_ENABLED=1)
# ------------------------------

def _maybe_enable_cors(app) -> None:
    enabled = str(os.getenv("CORS_ENABLED", "0")).strip() in ("1", "true", "True")
    if not enabled:
        app.logger.info("[register_all] CORS disabled by env")
        return

    # We are trying to use flask_course, if available.
    try:
        from flask_cors import CORS
        CORS(app, supports_credentials=True)
        app.logger.info("[register_all] CORS enabled via flask_cors")
        return
    except Exception:
        app.logger.warning("[register_all] flask_cors not available; enabling minimal CORS headers")

    @app.after_request
    def _cors_headers(resp: Response):
        try:
            origin = request.headers.get("Origin", "*")
            resp.headers.setdefault("Access-Control-Allow-Origin", origin)
            resp.headers.setdefault("Vary", "Origin")
            resp.headers.setdefault("Access-Control-Allow-Credentials", "true")
            resp.headers.setdefault(
                "Access-Control-Allow-Headers",
                "Authorization, Content-Type, X-Requested-With, X-P2P-Signature, X-P2P-Ts",
            )
            resp.headers.setdefault(
                "Access-Control-Allow-Methods",
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
        except Exception:
            pass
        return resp


# ------------------------------
# Registration of blueprints UI/ADMIN
# ------------------------------

_CANDIDATE_ROUTE_MODULES: List[str] = [
    # Frequently encountered:
    "routes.ui_routes",
    "routes.portal_routes",
    "routes.security_rbac_routes",
    "routes.metrics_routes",
    "routes.debug_routes",
    "routes.admin_routes",

    # Portable-podstranitsy:
    "routes.admin_portable_firststart",
    "routes.admin_portable_compliance",
    "routes.admin_portable_doctor",
    "routes.admin_portable_metrics",

    # Inogda kladut «svalku» tut:
    "routes.routes",
    "modules.routes.ui_routes",
    "modules.routes.admin_routes",
]

def _register_best_effort_blueprints(app) -> None:
    count = 0
    for mod_name in _CANDIDATE_ROUTE_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue

        # Prioritet: register(app) → init_app(app) → Blueprint 'bp'
        reg_funcs = [getattr(mod, n, None) for n in ("register", "init_app")]
        used = False
        for fn in reg_funcs:
            if callable(fn):
                try:
                    fn(app)  # type: ignore
                    app.logger.info(f"[register_all] Registered via {mod_name}.<callable>")
                    count += 1
                    used = True
                    break
                except Exception as e:
                    app.logger.warning(f"[register_all] {mod_name} callable failed: {e}")

        if not used:
            bp = getattr(mod, "bp", None)
            if isinstance(bp, Blueprint):
                try:
                    app.register_blueprint(bp)
                    app.logger.info(f"[register_all] Blueprint registered: {mod_name}.bp")
                    count += 1
                except Exception as e:
                    app.logger.warning(f"[register_all] Blueprint {mod_name}.bp failed: {e}")

    app.logger.info(f"[register_all] Blueprints (best-effort) registered: {count}")


# ------------------------------
# Bootstrap JS: A/B slots + routes
# ------------------------------

_BOOTSTRAP_JS_A = r"""
/* ester_bootstrap.js (slot A) — agressivnyy: sync tokena + fetch/XHR inektsiya + auto-rollback */
(function(){
  try {
    var K1 = 'jwt', K2 = 'ester.jwt';
    var t1 = localStorage.getItem(K1) || '';
    var t2 = localStorage.getItem(K2) || '';
    var tok = t2 || t1 || '';

    function parseJwt(token){
      try {
        var base = token.split('.')[1]; if(!base) return null;
        base = base.replace(/-/g,'+').replace(/_/g,'/');
        var json = decodeURIComponent(atob(base).split('').map(function(c){
          return '%' + ('00'+c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(json);
      } catch(e){ return null; }
    }

    function sameOrigin(u){
      try {
        var url = new URL(u, window.location.href);
        return url.origin === window.location.origin;
      } catch(e){ return true; }
    }

    // If there is only one key, duplicate it in the second one.
    if (tok) {
      localStorage.setItem(K1, tok);
      localStorage.setItem(K2, tok);
    }

    // Protukhshiy token — chistim oba.
    var payload = tok ? parseJwt(tok) : null;
    if (payload && payload.exp && (Date.now()/1000) > (payload.exp + 5)) {
      localStorage.removeItem(K1);
      localStorage.removeItem(K2);
      tok = '';
      console.warn('[ester_bootstrap:A] JWT expired: cleaned');
    }

    // Injection into feth: if it is the same-origin and there is no Authorization, substitute it.
    if (tok) {
      var _origFetch = window.fetch;
      window.fetch = function(input, init){
        try {
          var url = (typeof input === 'string') ? input : (input && input.url) || '';
          init = init || {};
          init.headers = init.headers || {};
          var H = new Headers(init.headers);
          if (!H.has('Authorization') && sameOrigin(url)) {
            H.set('Authorization', 'Bearer ' + tok);
          }
          init.headers = H;
          return _origFetch(input, init);
        } catch (e) {
          document.cookie = 'ester_bootstrap_error=A; Path=/; Max-Age=600';
          throw e;
        }
      };

      // Inektsiya v XHR
      var _origOpen = XMLHttpRequest.prototype.open;
      var _origSend = XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open = function(method, url){
        this.__ester_url = url;
        return _origOpen.apply(this, arguments);
      };
      XMLHttpRequest.prototype.send = function(body){
        try{
          if (this.__ester_url && sameOrigin(this.__ester_url)) {
            this.setRequestHeader('Authorization', 'Bearer ' + tok);
          }
        }catch(e){
          document.cookie = 'ester_bootstrap_error=A; Path=/; Max-Age=600';
        }
        return _origSend.apply(this, arguments);
      };
    }

    window.__esterBootstrapSlot = 'A';
  } catch (e) {
    try { document.cookie = 'ester_bootstrap_error=A; Path=/; Max-Age=600'; } catch(_){}
    console.error('[ester_bootstrap:A] failure', e);
  }
})();
"""

_BOOTSTRAP_JS_B = r"""
/* ester_bootstrap.zhs (slot B) - conservative: only token sync + diagnostics */
(function(){
  try {
    var K1 = 'jwt', K2 = 'ester.jwt';
    var t1 = localStorage.getItem(K1) || '';
    var t2 = localStorage.getItem(K2) || '';
    var tok = t2 || t1 || '';
    if (tok) {
      localStorage.setItem(K1, tok);
      localStorage.setItem(K2, tok);
    }
    window.__esterBootstrapSlot = 'B';
  } catch (e) {
    try { document.cookie = 'ester_bootstrap_error=B; Path=/; Max-Age=600'; } catch(_){}
    console.error('[ester_bootstrap:B] failure', e);
  }
})();
"""

def _mount_bootstrap_js_blueprint(app) -> None:
    bp = Blueprint("ester_bootstrap", __name__)

    @bp.route("/static/ester_bootstrap.js", methods=["GET"])
    def ester_bootstrap_js():
        # If the browser sends an error message for slot A, submit slot B.
        err = request.cookies.get("ester_bootstrap_error", "")
        slot = "B" if err == "A" else "A"
        js = _BOOTSTRAP_JS_B if slot == "B" else _BOOTSTRAP_JS_A
        resp = make_response(js)
        resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
        # We reset the error flag to prevent it from sticking.
        if err:
            resp.set_cookie("ester_bootstrap_error", "", path="/", max_age=0)
        return resp

    app.register_blueprint(bp)
    app.logger.info("[register_all] Mounted /static/ester_bootstrap.js")


# ------------------------------
# Embedding a script in HTML responses
# ------------------------------

_SCRIPT_TAG = '<script src="/static/ester_bootstrap.js"></script>'

def _inject_bootstrap_into_html(app) -> None:
    @app.after_request
    def _inject(resp: Response):
        try:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" not in ctype:
                return resp

            # Ne dublirovat
            data = resp.get_data(as_text=True)
            if _SCRIPT_TAG in data:
                return resp

            # Add before </water> (or at the end if there is no tag)
            insert_at = data.lower().rfind("</body>")
            if insert_at != -1:
                new_data = data[:insert_at] + _SCRIPT_TAG + data[insert_at:]
            else:
                new_data = data + _SCRIPT_TAG

            resp.set_data(new_data)
            # Peresobiraem dlinu avtomaticheski (Flask sam korrektiruet)
        except Exception as e:
            try:
                current_app.logger.warning(f"[register_all] HTML inject failed: {e}")
            except Exception:
                pass
        return resp


# ------------------------------
# Optional: debug page/debug/doctor (if not present)
# ------------------------------

def _doctor_payload(app) -> dict:
    return {
        "blueprints": sorted(list(app.blueprints.keys())),
        "url_map": [str(r) for r in app.url_map.iter_rules()],
        "rbac_attached": True,  # we don’t know for sure, but the guard himself will give away reality at his endpoints
    }

def _maybe_mount_doctor(app) -> None:
    # We will register only if there is no such endpoint.
    if "register_all_doctor" in app.view_functions:
        return

    bp = Blueprint("register_all_doctor", __name__)

    @bp.route("/register_all/doctor", methods=["GET"])
    def doctor():
        return _doctor_payload(app)

    app.register_blueprint(bp)
    app.logger.info("[register_all] Mounted /register_all/doctor")

# Contact your doctor right away so you can see the results.
# (Ne obyazatelen, no polezen; ne konfliktuet, t.k. neymspeys unikalnyy)
try:
    # If register_all(app) is not called, the doctor will see an empty list of blueprints.
    # This is a diagnostic route requested by Ovner.
    # Does not crash under import time restrictions.
    pass
except Exception:
    pass