from __future__ import annotations

"""
Ester JSON unicode adapter.

Tsel:
- V AB-rezhime B vklyuchat ensure_ascii=False dlya JSON-otvetov Flask,
  chtoby kirillitsa i prochiy Unicode otdavalis v chitaemom vide,
  a ne v "????" ili \\uXXXX-posledovatelnostyakh.

Povedenie:
- Po umolchaniyu (ESTER_JSON_UNICODE_AB != "B") — rezhim A: nichego ne trogaem.
- V rezhime B myagko patchim JSON-sloy Flask:
  * dlya legacy flask.json.dumps;
  * dlya app.json_provider_class (Flask 2.2+), pereopredelyaya dumps.

Garantii:
- Esli chto-to idet ne tak, adapter ne ronyaet prilozhenie.
- HTTP-kontrakty (struktura JSON, marshruty, polya) ne menyayutsya.
"""

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
    """
    Dlya starykh/sovmestimykh realizatsiy Flask:
    pereopredelyaem flask.json.dumps tak, chtoby ensure_ascii=False byl defoltom.
    """
    if flask_json is None:  # pragma: no cover
        return

    orig_dumps = getattr(flask_json, "dumps", None)
    if not callable(orig_dumps):
        return

    # Uzhe propatcheno — vykhodim.
    if getattr(flask_json, "_ester_unicode_patched", False):
        return

    def ester_dumps(obj: Any, **kwargs: Any) -> str:
        # Esli vyzyvayuschiy yavno ne ukazal ensure_ascii — vyklyuchaem ASCII-ekranirovanie.
        kwargs.setdefault("ensure_ascii", False)
        return orig_dumps(obj, **kwargs)  # type: ignore[misc]

    flask_json.dumps = ester_dumps  # type: ignore[assignment]
    setattr(flask_json, "_ester_unicode_patched", True)


def _patch_app_json_provider(app) -> None:
    """
    Dlya Flask 2.2+:
    podmenyaem json_provider_class tak, chtoby ensure_ascii=False byl defoltom.
    """
    if app is None:  # pragma: no cover
        return

    provider_class = getattr(app, "json_provider_class", None)
    if provider_class is None:
        return

    # Esli uzhe patchili — ne trogaem.
    if getattr(provider_class, "_ester_unicode_patched", False):
        return

    # Na sluchay otsutstviya novykh API — vse delaem maksimalno myagko.
    try:
        from flask.json.provider import JSONProvider  # type: ignore
    except Exception:  # pragma: no cover
        JSONProvider = object  # type: ignore

    # Esli tekuschiy provayder uzhe kakoy-to kastomnyy — prosto rasshiryaem ego.
    class EsterJSONProvider(provider_class):  # type: ignore[misc]
        _ester_unicode_patched = True

        def dumps(self, obj: Any, **kwargs: Any) -> str:  # type: ignore[override]
            # Ne lomaem yavnyy ensure_ascii ot vyzyvayuschego koda,
            # tolko menyaem defolt.
            kwargs.setdefault("ensure_ascii", False)
            return super().dumps(obj, **kwargs)

    # Veshaem novyy provayder na prilozhenie.
    app.json_provider_class = EsterJSONProvider

    # Initsializiruem app.json, esli eto primenimo dlya dannoy versii Flask.
    try:
        app.json = EsterJSONProvider(app)  # type: ignore[assignment]
    except Exception:  # pragma: no cover
        # Ne kritichno, glavnoe — provayder-klass.
        pass


def apply(app):
    """
    Tochka vkhoda dlya app.py.

    Upravlyaetsya peremennoy okruzheniya ESTER_JSON_UNICODE_AB:

      - "A" ili ne zadana:
            adapter zagruzhen, no ne aktiven (nichego ne patchim).
      - "B":
            vklyuchaem ensure_ascii=False dlya JSON-otvetov Flask tam,
            gde eto legitimno i bezopasno.

    Vozvraschaet:
        dict: {"ok": bool, "mode": "A"|"B"}
    """
    mode = (os.getenv("ESTER_JSON_UNICODE_AB", "A") or "A").strip().upper()

    if mode != "B":
        # Rezhim A: nichego ne trogaem.
        return {"ok": True, "mode": "A"}

    try:
        _patch_flask_json_global()
        _patch_app_json_provider(app)
        return {"ok": True, "mode": "B"}
    except Exception as e:  # pragma: no cover
        # Fail-safe: Ester dolzhna rabotat dazhe pri sboe adaptera.
        try:
            print("[ester-json/unicode] error:", e)
        except Exception:
            pass
        return {"ok": False, "mode": mode}