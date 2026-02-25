from __future__ import annotations

"""Ester JSON unicode adapter.

Tsel:
- V AB-rezhime B vklyuchat ensure_ascii=False dlya JSON-otvetov Flask,
  chtoby kirillitsa i prochiy Unicode otdavalis v chitaemom vide,
  a ne v "????" ili\\uXXXX-posledovatelnostyakh.

Behavior:
- Po umolchaniyu (ESTER_JSON_UNICODE_AB != "B") - rezhim A: nichego ne trogaem.
- V rezhime B myagko patchim JSON-layer Flask:
  * dlya legacy flask.json.dumps;
  * for app.jsion_provider_class (Flask 2.2+), overriding dumps.

Guarantee:
- Esli chto-to idet ne tak, adapter ne ronyaet prilozhenie.
- HTTP-contrakty (struktura JSON, route, polya) ne menyayutsya."""

import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import flask  # type: ignore
    import flask.json as flask_json  # type: ignore
except Exception:  # pragma: no cover
    flask = None  # type: ignore
    flask_json = None  # type: ignore


def _patch_flask_json_global() -> None:
    """For older/compatible Flask implementations:
    override flask.jsion.dumps so that sensor_assy=false is the default."""
    if flask_json is None:  # pragma: no cover
        return

    orig_dumps = getattr(flask_json, "dumps", None)
    if not callable(orig_dumps):
        return

    # Already patched - let's go.
    if getattr(flask_json, "_ester_unicode_patched", False):
        return

    def ester_dumps(obj: Any, **kwargs: Any) -> str:
        # If the caller has not explicitly specified an sensor_assy, ​​turn off the ASSIY shielding.
        kwargs.setdefault("ensure_ascii", False)
        return orig_dumps(obj, **kwargs)  # type: ignore[misc]

    flask_json.dumps = ester_dumps  # type: ignore[assignment]
    setattr(flask_json, "_ester_unicode_patched", True)


def _patch_app_json_provider(app) -> None:
    """For Flask 2.2+:
    overrides jsion_provider_class so that sensor_assy=False is the default."""
    if app is None:  # pragma: no cover
        return

    provider_class = getattr(app, "json_provider_class", None)
    if provider_class is None:
        return

    # If we've already patched it, don't touch it.
    if getattr(provider_class, "_ester_unicode_patched", False):
        return

    # In case there are no new APIs, we do everything as gently as possible.
    try:
        from flask.json.provider import JSONProvider  # type: ignore
    except Exception:  # pragma: no cover
        JSONProvider = object  # type: ignore

    # If the current provider is already some kind of custom one, we simply expand it.
    class EsterJSONProvider(provider_class):  # type: ignore[misc]
        _ester_unicode_patched = True

        def dumps(self, obj: Any, **kwargs: Any) -> str:  # type: ignore[override]
            # We don’t break the explicit sensor_assy from the calling code,
            # We just change the default.
            kwargs.setdefault("ensure_ascii", False)
            return super().dumps(obj, **kwargs)

    # We attach a new provider to the application.
    app.json_provider_class = EsterJSONProvider

    # Initializes app.jsion, if applicable for this version of Flask.
    try:
        app.json = EsterJSONProvider(app)  # type: ignore[assignment]
    except Exception:  # pragma: no cover
        # Ne kritichno, glavnoe — provayder-klass.
        pass


def apply(app):
    """Tochka vkhoda dlya app.py.

    Upravlyaetsya peremennoy okruzheniya ESTER_JSON_UNICODE_AB:

      - "A" or ne zadana:
            adapter zagruzhen, no ne aktiven (nichego ne patchim).
      - "B":
            vklyuchaem ensure_ascii=False dlya JSON-otvetov Flask tam,
            where it is legitimno and safe.

    Vozvraschaet:
        dict: {"ok": bool, "mode": "A"|"B"}"""
    mode = (os.getenv("ESTER_JSON_UNICODE_AB", "A") or "A").strip().upper()

    if mode != "B":
        # Mode A: don't touch anything.
        return {"ok": True, "mode": "A"}

    try:
        _patch_flask_json_global()
        _patch_app_json_provider(app)
        return {"ok": True, "mode": "B"}
    except Exception as e:  # pragma: no cover
        # File-safe: Esther should work even if the adapter fails.
        try:
            print("[ester-json/unicode] error:", e)
        except Exception:
            pass
        return {"ok": False, "mode": mode}