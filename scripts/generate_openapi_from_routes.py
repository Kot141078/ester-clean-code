# -*- coding: utf-8 -*-
"""
scripts/generate_openapi_from_routes.py — generator OpenAPI.yaml iz Flask-marshrutov.

Zapusk:
  python scripts/generate_openapi_from_routes.py  # sozdast docs/OpenAPI.yaml

Osobennosti:
- Ne menyaet kod prilozheniya, chitaet kartu marshrutov iz app.url_map.
- Ignoriruet /static/*, HEAD/OPTIONS.
- Sozdaet minimalno sovmestimoe opisanie OpenAPI 3.0.0, prigodnoe dlya Swagger UI.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import yaml  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from app import app  # type: ignore
except Exception as e:
    raise SystemExit(f"Cannot import Flask app: {e}")


def build_spec() -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    for rule in app.url_map.iter_rules():  # type: ignore[attr-defined]
        path = str(rule)
        if path.startswith("/static/"):
            continue
        methods = [m for m in rule.methods if m not in ("HEAD", "OPTIONS")]
        path_item: Dict[str, Any] = paths.setdefault(path, {})
        for m in methods:
            op = m.lower()
            path_item[op] = {
                "summary": f"{m} {path}",
                "responses": {
                    "200": {"description": "OK"},
                    "4XX": {"description": "Client error"},
                    "5XX": {"description": "Server error"},
                },
            }

    spec: Dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {
            "title": "Ester API",
            "version": "0.1.0",
            "description": "Avtosgenerirovannoe opisanie po tekuschim marshrutam Flask.",
        },
        "servers": [{"url": "/"}],
        "paths": paths,
    }
    return spec


def main():
    spec = build_spec()
    out_dir = os.path.join(os.getcwd(), "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "OpenAPI.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True)
    print(f"Wrote {out_path} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()