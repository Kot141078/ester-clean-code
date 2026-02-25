# -*- coding: utf-8 -*-
import json

import pytest

from app import create_app  # fabrika est v dampe
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _auth_token(client, role="replicator"):
    # V dampe est /auth/login c rolyami
    r = client.post("/auth/login", json={"user": "pytest", "role": role})
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert "access_token" in data
    return data["access_token"]


def test_state_and_pull_by_ids_flow():
    app = create_app()
    with app.test_client() as c:
        # /p2p/state dostupen bez strogoy avtorizatsii
        r = c.get("/p2p/state?level=0")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "levels_count" in data

        # Authorizes for add/bullet_ids
        token = _auth_token(c, role="replicator")
        headers = {"Authorization": f"Bearer {token}"}

        # Dobavim zapis v CRDT
        r_add = c.post(
            "/p2p/mem/add",
            headers=headers,
            json={"id": "test:1", "payload": {"topic": "p2p", "t": "hello"}},
        )
        assert r_add.status_code == 200
        da = r_add.get_json()
        assert da["ok"] is True

        # Vytaschim ee po pull_by_ids
        r_pull = c.post("/p2p/pull_by_ids", headers=headers, json={"ids": ["test:1"]})
        assert r_pull.status_code == 200
        dp = r_pull.get_json()
        assert dp["ok"] is True
        assert "entries" in dp and "test:1" in dp["entries"]
        assert dp["entries"]["test:1"]["item"]["id"] == "test:1"


def test_sync_run_endpoint():
    app = create_app()
    with app.test_client() as c:
        token = _auth_token(c, role="replicator")
        headers = {"Authorization": f"Bearer {token}"}
        r = c.post("/p2p/sync/run", headers=headers)
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "result" in data
        assert "visited" in data["result"]
