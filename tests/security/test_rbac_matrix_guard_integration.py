# -*- coding: utf-8 -*-
"""
tests/security/test_rbac_matrix_guard_integration.py — integratsionnyy test RBAC-guard.

Ideya: dobavlyaem testovyy marshrut /ops/_test_guard, vklyuchaem before_request-guard iz rbac_matrix,
inzhektim roli cherez zagolovok X-Test-Roles -> g.user_roles i proveryaem, chto:
  - user -> 403
  - admin -> 200
"""
from __future__ import annotations

import textwrap
from flask import Blueprint, Flask, g, jsonify, request  # type: ignore

from security.rbac_matrix import register_rbac_matrix  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_rbac_guard_blocks_user_allows_admin(tmp_path):
    flask_app = Flask(__name__)
    matrix_path = tmp_path / "rbac_matrix.yaml"
    matrix_path.write_text(
        textwrap.dedent(
            """
            roles:
              admin:
                allow: ["*"]
              ops:
                allow: ["/ops/*"]
            rules:
              "/ops/*":
                require_any_role: ["admin", "ops"]
            """
        ).strip(),
        encoding="utf-8",
    )

    # Testovyy marshrut v zone /ops/*
    bp = Blueprint("rbac_test_ops", __name__)

    @bp.get("/ops/_test_guard")
    def _ops_test_guard():
        return jsonify({"ok": True, "msg": "allowed"})

    flask_app.register_blueprint(bp)

    # Inzhektor roley iz zagolovka pered RBAC-khukom
    @flask_app.before_request
    def _inject_roles_from_header():
        roles = request.headers.get("X-Test-Roles", "")
        g.user_roles = [r.strip() for r in roles.split(",") if r.strip()]

    register_rbac_matrix(flask_app, path=str(matrix_path))

    c = flask_app.test_client()

    # user — zapret
    r1 = c.get("/ops/_test_guard", headers={"X-Test-Roles": "user"})
    assert r1.status_code == 403

    # admin — dopusk
    r2 = c.get("/ops/_test_guard", headers={"X-Test-Roles": "admin"})
    assert r2.status_code == 200
# assert r2.get_json().get("ok") is True
