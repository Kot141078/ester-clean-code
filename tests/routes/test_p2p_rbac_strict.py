# -*- coding: utf-8 -*-
import importlib
import json
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _auth_token(client, role):
    r = client.post("/auth/login", json={"user": "pytest", "role": role})
    assert r.status_code in (200, 201)
    return r.get_json()["access_token"]


def test_push_requires_replicator_when_strict(monkeypatch):
    # Enable strict mode before importing a module with blueprint
    monkeypatch.setenv("ESTER_RBAC_STRICT", "1")
    # Reload the route module so that RVACH_STRICT is read from the env
    import routes.p2p_crdt_routes as p2p_mod  # noqa

    importlib.reload(p2p_mod)

    from app import create_app

    app = create_app()
    with app.test_client() as c:
        # Token bez roli replicator
        t_user = _auth_token(c, role="user")
        r_forbidden = c.post(
            "/p2p/push", headers={"Authorization": f"Bearer {t_user}"}, json={"ops": []}
        )
        assert r_forbidden.status_code in (401, 403)

        # Token s rolyu replicator
        t_rep = _auth_token(c, role="replicator")
        r_ok = c.post("/p2p/push", headers={"Authorization": f"Bearer {t_rep}"}, json={"ops": []})
        # If XMAS is turned off (by default) it should pass
        assert r_ok.status_code == 200
# assert r_ok.get_json()["ok"] is True