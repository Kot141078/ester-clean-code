# -*- coding: utf-8 -*-
"""
routes/docs_routes.py — Swagger UI na /docs Re JSON speka na /openapi.json.
Drop-in: otdelnyy blyuprint; podklyuchite v app.py:
    from routes.docs_routes import bp_docs
    app.register_blueprint(bp_docs)

Povedenie /openapi.json:
- Ischet spetsifikatsiyu po putyam (v poryadke prioriteta):
    1) ENV OPENAPI_SPEC_PATH (esli zadan)
    2) docs/OpenAPI.yaml
    3) docs/openapi.yaml
    4) openapi.yaml
    5) openapi.yml
    6) docs/OpenAPI.yml
    7) docs/openapi.yml
    8) openapi.json
    9) docs/openapi.json
- Podderzhivaet YAML (cherez PyYAML) i JSON.
- Bozvraschaet application/json, pretty-printed.
- Esli spetsifikatsiya ne naydena ili ne parsitsya — daet ponyatnuyu JSON-oshibku.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from flask import Blueprint, Response, jsonify, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_docs = Blueprint("docs", __name__)


@bp_docs.get("/docs")
def docs_index():
    # Shablon soderzhit <div id="swagger-ui"></div>, chto ozhidayut testy
    return render_template("docs_swagger.html")


@bp_docs.get("/openapi.json")
def openapi_json():
    spec_path = _find_openapi_path()
    if spec_path is None:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "OpenAPI spec not found",
                    "searched": _candidate_paths(),
                }
            ),
            404,
        )

    try:
        data = _load_spec(spec_path)
    except (
        Exception
    ) as e:  # noqa: BLE001 — khotim vernut ponyatnuyu oshibku polzovatelyu
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Failed to parse spec: {e.__class__.__name__}: {e}",
                    "path": spec_path,
                }
            ),
            500,
        )

    # Otdaem kak JSON (pretty), soblyudaya UTF-8
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json; charset=utf-8")


# -------------------------
# Bnutrennie pomoschniki
# -------------------------
def _candidate_paths() -> List[str]:
    env_path = os.environ.get("OPENAPI_SPEC_PATH")
    candidates: List[str] = []
    if env_path:
        candidates.append(env_path)

    # Naibolee chastye imena/puti
    candidates.extend(
        [
            "openapi.yaml",
            "openapi.yml",
            os.path.join("docs", "OpenAPI.yaml"),
            os.path.join("docs", "openapi.yaml"),
            os.path.join("docs", "OpenAPI.yml"),
            os.path.join("docs", "openapi.yml"),
            "openapi.json",
            os.path.join("docs", "openapi.json"),
        ]
    )
    # Uberem dublikaty, sokhraniv poryadok
    seen = set()
    uniq: List[str] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _find_openapi_path() -> Optional[str]:
    for p in _candidate_paths():
        if os.path.isfile(p):
            return p
    return None


def _load_spec(path: str):
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        raw = f.read()

    if ext in (".yaml", ".yml"):
        # PyYAML obyazatelen dlya YAML; v proekte uzhe ispolzuetsya YAML v pravilakh/konfige.
        try:
            import yaml  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"PyYAML is required to parse YAML specs but is not available: {e}")
        return yaml.safe_load(raw)

    # JSON po umolchaniyu
# return json.loads(raw.decode("utf-8"))


def register(app):
    app.register_blueprint(bp_docs)
    return app
