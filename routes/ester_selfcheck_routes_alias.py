# -*- coding: utf-8 -*-
"""routes/ester_selfcheck_routes_alias.py

Edinyy self-check Ester.

GET /ester/selfcheck

Aggregate:
- /ester/thinking/manifest
- /ester/thinking/status
- /ester/thinking/quality_once (probnyy vyzov, esli dostupen bezopasno)
- /ester/will/status
- /ester/memory/status

Realizatsiya:
- Use internal test_client(), ne external HTTP.
- Ne menyaet otvety bazovykh marshrutov.
- Lyubye oshibki prevraschaet v warnings, ne lomaya yadro.

Mosty:
- Yavnyy: Myshlenie + Memory + Volya ↔ edinyy status.
- Skrytyy #1: Self-check ↔ Planirovschik — mozhno dergat kak ezhednevnyy test.
- Skrytyy #2: Self-check ↔ chelovek-operator — odin vzglyad vmesto razroznennykh proverok.

Zemnoy abzats:
Kak kontrolnaya panel na stoyke serverov: sobiraet lampochki voedino,
no ne upravlyaet pitaniem napryamuyu."""

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, current_app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _probe(client, method: str, path: str, json_body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": False,
        "code": None,
        "error": None,
    }
    try:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=json_body or {})
        result["code"] = resp.status_code
        if 200 <= resp.status_code < 300:
            result["ok"] = True
        else:
            result["error"] = f"status_{resp.status_code}"
    except Exception as e:  # pragma: no cover
        result["error"] = f"exception:{e!s}"
    return result


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_selfcheck_routes", __name__, url_prefix="/ester")

    @bp.get("/selfcheck")
    def ester_selfcheck() -> Any:
        app = current_app._get_current_object()
        client = app.test_client()

        checks: Dict[str, Dict[str, Any]] = {}
        warnings = []

        # thinking manifest
        checks["thinking_manifest"] = _probe(client, "GET", "/ester/thinking/manifest")

        # thinking status (trace)
        checks["thinking_status"] = _probe(client, "GET", "/ester/thinking/status")

        # thinking quality (optsionalno)
        q = _probe(
            client,
            "POST",
            "/ester/thinking/quality_once",
            {"prompt": "internal self-check probe"},
        )
        # We don’t consider 404/405 an architectural error
        if not q["ok"] and q.get("code") in (404, 405):
            q["ok"] = True
            q["note"] = "quality_endpoint_optional"
        checks["thinking_quality_once"] = q

        # will status
        checks["will_status"] = _probe(client, "GET", "/ester/will/status")

        # memory status (may be absent)
        m = _probe(client, "GET", "/ester/memory/status")
        if not m["ok"] and m.get("code") in (404, 405):
            m["ok"] = True
            m["note"] = "memory_status_optional"
        checks["memory_status"] = m

        # Itogovyy ok = vse obyazatelnye bloki ok.
        mandatory = ("thinking_manifest", "will_status")
        ok = True
        for key in mandatory:
            if not checks.get(key, {}).get("ok"):
                ok = False
                warnings.append(f"{key}_failed")

        # If the thinking_status or gate_status is not ok - a warning.
        if not checks["thinking_status"]["ok"]:
            warnings.append("thinking_status_warn")
        if not checks["thinking_quality_once"]["ok"]:
            note = checks["thinking_quality_once"].get("note")
            if note != "quality_endpoint_optional":
                warnings.append("thinking_quality_warn")
        if not checks["memory_status"]["ok"]:
            note = checks["memory_status"].get("note")
            if note != "memory_status_optional":
                warnings.append("memory_status_warn")

        out: Dict[str, Any] = {
            "ok": ok,
            "checks": checks,
            "warnings": warnings,
        }
        return jsonify(out)

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-selfcheck/routes] registered /ester/selfcheck")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]