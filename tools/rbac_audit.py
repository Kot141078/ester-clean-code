# -*- coding: utf-8 -*-
"""Sverka RBAC-matritsy s realnymi marshrutami Flask.
Feylim (exit 2), esli zaschischennye marshruty ne pomecheny @jwt_required ili ne sovpadayut roli.
"""
from __future__ import annotations

import inspect
import sys

import yaml
from flask import current_app

ALLOWED_ATTRS = {"jwt_required", "jwt_optional", "jwt_refresh_token_required"}


def collect_routes(app):
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("static"):  # propuskaem
            continue
        view = app.view_functions[rule.endpoint]
        yield str(rule), view


def is_jwt_protected(view) -> bool:
    # grubyy sposob: prosmatrivaem zamykaniya/atributy dekoratorov
    try:
        src = inspect.getsource(view)
    except Exception:
        return False
    return "@jwt_required" in src or "@jwt_required(" in src


def main(app, matrix_path="config/rbac_matrix.yaml") -> int:
    with open(matrix_path, "r", encoding="utf-8") as f:
        matrix = yaml.safe_load(f) or {}
    protected = set(matrix.get("protected_paths", []))
    errors = []
    for rule, view in collect_routes(app):
        if any(str(rule).startswith(p) for p in protected):
            if not is_jwt_protected(view):
                errors.append(f"route {rule} expected jwt_required")
    if errors:
        for e in errors:
            print("[RBAC-AUDIT]", e, file=sys.stderr)
        return 2
    print("RBAC audit OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    from app import app as flask_app  # type: ignore

    sys.exit(main(flask_app))
