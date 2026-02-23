# -*- coding: utf-8 -*-
# bootstrap/jwt_setup.py
"""
bootstrap/jwt_setup.py — idempotentnaya nastroyka JWT dlya Flask-prilozheniya.

Naznachenie:
  • Bezopasno initsializirovat flask_jwt_extended.JWTManager(app), esli on esche ne initsializirovan.
  • Ustanovit algoritm/sekrety iz okruzheniya (HS256 po umolchaniyu); sovmestimo s konfigom iz app.py.
  • Predostavit edinyy ensure_jwt(app), kotoryy mozhno smelo vyzyvat neskolko raz.

Sovmestimost:
  • Esli RS256 vybran cherez peremennye, klyuchi chitayutsya iz JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH.
  • Esli biblioteka nedostupna — funktsiya myagko zavershaetsya (nikakikh import-oshibok naruzhu).

Zemnoy abzats (inzheneriya):
Odin vyklyuchatel dlya «shin» autentifikatsii — isklyuchaet raskhozhdeniya mezhdu modulyami, gde nuzhna JWT-podpis.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): edinyy regulyator JWT-podsistemy.
- Skrytyy 1 (Infoteoriya ↔ Interfeysy): povtornyy vyzov ne povyshaet «shum» i ne lomaet uzhe nastroennoe.
- Skrytyy 2 (Anatomiya ↔ PO): kak gormonalnaya regulyatsiya — odna nastroyka deystvuet na ves organizm.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask_jwt_extended import JWTManager  # type: ignore
except Exception:  # pragma: no cover
    JWTManager = None  # type: ignore


def _truthy(v: Any) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on", "y")


def _lab_mode_enabled() -> bool:
    return _truthy(os.getenv("ESTER_LAB_MODE", "0"))


def _jwt_enabled(app) -> bool:
    env_enabled = os.getenv("JWT_ENABLED")
    if env_enabled is not None and str(env_enabled).strip():
        return _truthy(env_enabled)
    cfg_enabled = app.config.get("JWT_ENABLED")
    if cfg_enabled is not None:
        return _truthy(cfg_enabled) if isinstance(cfg_enabled, str) else bool(cfg_enabled)
    # Yavno zadannyy algoritm schitaem priznakom vklyuchennogo JWT.
    if str(os.getenv("JWT_ALG", "")).strip():
        return True
    if str(app.config.get("JWT_ALGORITHM", "")).strip():
        return True
    return False


def ensure_jwt(app) -> None:
    if app.extensions and app.extensions.get("flask-jwt-extended"):
        return

    if not _jwt_enabled(app):
        return

    if not JWTManager:
        if _lab_mode_enabled():
            app.logger.warning(
                "JWT is enabled but flask_jwt_extended is unavailable; "
                "continuing in LAB mode without JWT init"
            )
            return
        raise RuntimeError("JWT is enabled but flask_jwt_extended is not installed")

    alg = (os.getenv("JWT_ALG") or app.config.get("JWT_ALGORITHM") or "HS256").upper()
    app.config["JWT_ALGORITHM"] = alg
    if alg == "RS256":
        priv_path = os.getenv("JWT_PRIVATE_KEY_PATH")
        pub_path = os.getenv("JWT_PUBLIC_KEY_PATH")
        if not (priv_path and pub_path and os.path.exists(priv_path) and os.path.exists(pub_path)):
            if _lab_mode_enabled():
                app.logger.warning(
                    "RS256 selected but key paths are missing; "
                    "continuing in LAB mode without JWT init"
                )
                return
            raise RuntimeError("RS256 selected but keys not provided")
        app.config["JWT_PRIVATE_KEY"] = open(priv_path, "r", encoding="utf-8").read()
        app.config["JWT_PUBLIC_KEY"] = open(pub_path, "r", encoding="utf-8").read()
    else:
        secret = (
            app.config.get("JWT_SECRET_KEY")
            or os.getenv("JWT_SECRET_KEY")
            or os.getenv("JWT_SECRET")
        )
        if not secret:
            if _lab_mode_enabled():
                app.logger.warning(
                    "JWT enabled without JWT_SECRET_KEY/JWT_SECRET; "
                    "using lab-only unsafe secret for startup"
                )
                secret = "ester-lab-unsafe-jwt-secret"
            else:
                raise RuntimeError(
                    "JWT is enabled but JWT_SECRET_KEY/JWT_SECRET is not set"
                )
        app.config["JWT_SECRET_KEY"] = secret

    JWTManager(app)
