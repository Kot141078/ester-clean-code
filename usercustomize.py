# -*- coding: utf-8 -*-
"""usercustomize - ranniy bootstrap dlya offlayn-sborki Ester (polnaya versiya C/paket-07).

What do you do (korotko):
  • builtins.a/b - strakhovka ot NameError.
  • Guard duplicate Blueprint v verify-rezhime (ESTER_VERIFY_ALLOW_DUP_BP=1).
  • JWT-sovmestimost: addvlyaet verify_jwt_in_request_optional pri otsutstvii.
  • ENV-primer (A/B): po umolchaniyu “shirokiy” rezhim A — zamenyaet None na '' DLYa LYuBOGO os.getenv(),
    rezhim B - tolko suffiksy *_PREFIX/_URL/_BASE/_HOST/_PORT/_DIR/_PATH (pereklyuchatel ESTER_ENV_PRIMER_SLOT=B).
  • Psevdo-paketnyy shim dlya `modules.scheduler` i podmodulya `modules.scheduler.watcher` cherez MetaPathFinder —
    garantiruet uspeshnyy import “watcher” dazhe pri nalichii odnoimennogo fayla-perekrytiya.
  • Myagkie patchi pri otsutstvii simvolov:
      - modules.scheduler_engine: start/stop/status/schedule/cancel
      - modules.ingest.common: build_mm_from_env
      - routes.telegram_webhook_routes: register_telegram_webhook
      - security.signing: get_hmac_key/header_signature/key_id
  • VAZhNO: my NE delaem ranniy `import routes`, chtoby ne provotsirovat “partial init” tsiklov importa.

MOSTY:
- Yavnyy: (Importnaya sistema ↔ Routy) - guard blyuprintov + MetaPathFinder dlya scheduler(watcher).
- Skrytyy #1: (OS-okruzhenie ↔ Konstruktory URL/putey) - ENV-primer ustranyaet `None + None`.
- Skrytyy #2: (Kontrakty ↔ Simvoly) - dobor ozhidaemykh API bez izmeneniya import-putey.

ZEMNOY ABZATs:
Eto “schitok s predokhranitelyami i perekhodnikami”: ubiraem koltsa importa, podkidyvaem nedostayuschie klemmy i
zaschischaem sborku ot pustykh peremennykh okruzheniya. Bezdiskovaya "ramka" dlya `modules.scheduler.watcher`
pozvolyaet adminke gruzitsya nezavisimo ot faylovoy geometrii.

# c=a+b"""
from __future__ import annotations

import os
import sys
import types
import hashlib
import hmac
import importlib
import importlib.abc
import importlib.machinery
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ──────────────────────────────────────────────────────────────────────────────
# 0) builtins a/b — strakhovka
# ──────────────────────────────────────────────────────────────────────────────
try:
    import builtins  # type: ignore
    builtins.a = getattr(builtins, "a", None)
    builtins.b = getattr(builtins, "b", None)
except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────────────
# 1) Blueprint Guard (only in verification mode)
# ──────────────────────────────────────────────────────────────────────────────
def _install_blueprint_guard_fallback() -> None:
    try:
        from flask import Flask  # type: ignore
        if getattr(Flask, "register_blueprint__safe", False):
            return
        _ORIG = Flask.register_blueprint

        def _safe_register(self, bp, *a, **k):
            try:
                return _ORIG(self, bp, *a, **k)
            except Exception as e:  # noqa: BLE001
                s = str(e)
                if ("already registered" in s) or ("The name" in s and "is already registered" in s):
                    try:
                        print(
                            f"[usercustomize.guard] skip duplicate blueprint: {getattr(bp, 'name', 'bp')}",
                            file=sys.stderr,
                        )
                    except Exception:
                        pass
                    return None
                raise

        Flask.register_blueprint = _safe_register  # type: ignore[attr-defined]
        setattr(Flask, "register_blueprint__safe", True)
    except Exception:
        pass


def _install_blueprint_guard_if_requested() -> None:
    if os.getenv("ESTER_VERIFY_ALLOW_DUP_BP") == "1":
        try:
            import tools.blueprint_guard as _bg  # noqa: F401
            _bg.install_blueprint_guard()  # type: ignore[attr-defined]
        except Exception:
            _install_blueprint_guard_fallback()


_install_blueprint_guard_if_requested()


# ──────────────────────────────────────────────────────────────────────────────
# 2) JWT-sovmestimost: verify_jwt_in_request_optional
# ──────────────────────────────────────────────────────────────────────────────
def _install_jwt_optional_verify() -> None:
    try:
        import flask_jwt_extended as _jwt  # type: ignore
        if hasattr(_jwt, "verify_jwt_in_request_optional"):
            return
        try:
            from flask_jwt_extended import verify_jwt_in_request  # type: ignore

            def verify_jwt_in_request_optional(*args, **kwargs):
                try:
                    return verify_jwt_in_request(optional=True)
                except TypeError:
                    try:
                        return verify_jwt_in_request()
                    except Exception:
                        return None

            _jwt.verify_jwt_in_request_optional = verify_jwt_in_request_optional  # type: ignore[attr-defined]
        except Exception:
            def verify_jwt_in_request_optional(*args, **kwargs):  # noqa: D401
                return None
            _jwt.verify_jwt_in_request_optional = verify_jwt_in_request_optional  # type: ignore[attr-defined]
    except Exception:
        pass


_install_jwt_optional_verify()


# ──────────────────────────────────────────────────────────────────────────────
# 3) ENV-primer (A/B-sloty)
#    A (default): replaces None with b for Any getenv key
#    B: ogranichennyy nabor suffiksov
#    Pereklyuchatel: ESTER_ENV_PRIMER_SLOT=A|B  (defolt: A)
# ──────────────────────────────────────────────────────────────────────────────
def _install_env_primer() -> None:
    import os as _os
    slot = (str(_os.getenv("ESTER_ENV_PRIMER_SLOT") or "A")).upper()
    _orig_getenv = _os.getenv

    _suffixes = ("_PREFIX", "_URL", "_BASE", "_HOST", "_PORT", "_DIR", "_PATH")

    def _safe_getenv_any(key, default=None):  # noqa: ANN001
        v = _orig_getenv(key, default)
        return "" if v is None else v

    def _safe_getenv_suffix(key, default=None):  # noqa: ANN001
        v = _orig_getenv(key, default)
        if v is None and any(key.endswith(s) for s in _suffixes):
            return ""
        return v

    _os.getenv = _safe_getenv_any if slot == "A" else _safe_getenv_suffix  # type: ignore[assignment]


try:
    _install_env_primer()
except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────────────
# 4) MetaPatnFinder for the modules.scheduler pseudo-package (+ watcher)
#    Reshaet: "No module named 'modules.scheduler.watcher'; 'modules.scheduler' is not a package"
# ──────────────────────────────────────────────────────────────────────────────
class _SchedulerShimFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    pkg_name = "modules.scheduler"
    watcher_name = "modules.scheduler.watcher"

    def find_spec(self, fullname, path=None, target=None):  # noqa: D401, ANN001
        # If a real module/package has already been found by a standard search, it does not interfere
        real = importlib.machinery.PathFinder.find_spec(fullname, path)
        if real is not None:
            return None

        if fullname == self.pkg_name:
            # Returning the PACKAGE specification
            spec = importlib.machinery.ModuleSpec(
                name=fullname,
                loader=self,
                is_package=True,
            )
            spec.submodule_search_locations = []  # tipovoy marker paketa
            return spec

        if fullname == self.watcher_name:
            # Returning the specification of a regular module
            return importlib.machinery.ModuleSpec(
                name=fullname,
                loader=self,
                is_package=False,
            )
        return None

    # noinspection PyUnusedLocal
    def create_module(self, spec):  # noqa: D401, ANN001
        return None  # default sozdast novyy obekt modulya

    # noinspection PyUnusedLocal
    def exec_module(self, module):  # noqa: D401, ANN001
        if module.__name__ == self.pkg_name:
            # Marks as package
            module.__package__ = self.pkg_name
            module.__path__ = []  # type: ignore[attr-defined]
            return
        if module.__name__ == self.watcher_name:
            module.__package__ = self.pkg_name

            def status():
                return {"ok": True, "watcher": "stub"}

            def start():
                return {"ok": True, "started": True}

            def stop():
                return {"ok": True, "stopped": True}

            module.status = status  # type: ignore[attr-defined]
            module.start = start    # type: ignore[attr-defined]
            module.stop = stop      # type: ignore[attr-defined]
            return


# Ustanavlivaem shim odin raz
try:
    if not any(isinstance(f, _SchedulerShimFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _SchedulerShimFinder())
except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────────────
# 5) Soft monkey patch missing characters
# ──────────────────────────────────────────────────────────────────────────────

# 5.1) modules.scheduler_engine: start/stop/status/schedule/cancel
try:
    import modules.scheduler_engine as _se  # type: ignore

    if not hasattr(_se, "start"):
        def start(*a, **k): return {"ok": True, "started": True}
        _se.start = start  # type: ignore[attr-defined]
    if not hasattr(_se, "stop"):
        def stop(*a, **k): return {"ok": True, "stopped": True}
        _se.stop = stop  # type: ignore[attr-defined]
    if not hasattr(_se, "status"):
        def status(*a, **k): return {"ok": True, "status": "idle"}
        _se.status = status  # type: ignore[attr-defined]
    if not hasattr(_se, "schedule"):
        def schedule(*a, **k): return {"ok": True, "plan": []}
        _se.schedule = schedule  # type: ignore[attr-defined]
    if not hasattr(_se, "cancel"):
        def cancel(job_id=None):  # noqa: ANN001
            return {"ok": True, "canceled": 0 if not job_id else 1, "job_id": job_id}
        _se.cancel = cancel  # type: ignore[attr-defined]
except Exception:
    pass

# 5.2) modules.ingest.common: build_mm_from_env
try:
    import modules.ingest.common as _ing_common  # type: ignore
    if not hasattr(_ing_common, "build_mm_from_env"):
        def build_mm_from_env(*a, **k): return {}
        _ing_common.build_mm_from_env = build_mm_from_env  # type: ignore[attr-defined]
except Exception:
    pass

# 5.3) routes.telegram_webhook_routes: register_telegram_webhook
try:
    import routes.telegram_webhook_routes as _tgw  # type: ignore
    if not hasattr(_tgw, "register_telegram_webhook"):
        def register_telegram_webhook(*a, **k): return True
        _tgw.register_telegram_webhook = register_telegram_webhook  # type: ignore[attr-defined]
except Exception:
    pass

# 5.4) security.signing: garantiruem get_hmac_key/header_signature/key_id
try:
    import security.signing as _sign  # type: ignore

    if not hasattr(_sign, "get_hmac_key"):
        def get_hmac_key() -> str:
            return "ester-offline-hmac-key"
        _sign.get_hmac_key = get_hmac_key  # type: ignore[attr-defined]

    if not hasattr(_sign, "header_signature"):
        def header_signature(headers: dict | None = None) -> str:
            headers = headers or {}
            msg = "\n".join(f"{k}:{headers[k]}" for k in sorted(headers))
            return hmac.new(_sign.get_hmac_key().encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        _sign.header_signature = header_signature  # type: ignore[attr-defined]

    if not hasattr(_sign, "key_id"):
        def key_id() -> str:
            # Compact key identifier (first 12 hash characters ША256)
            digest = hashlib.sha256(_sign.get_hmac_key().encode("utf-8")).hexdigest()
            return digest[:12]
        _sign.key_id = key_id  # type: ignore[attr-defined]

except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────────────
# 6) Important: NO early imports - avoid “partial init” import cycles
# ──────────────────────────────────────────────────────────────────────────────
# We don't import anything here. Let the app/infrastructure do it.

# c=a+b