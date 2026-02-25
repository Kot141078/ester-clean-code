# -*- coding: utf-8 -*-
import json

from app import create_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _auth_token(client, role="replicator"):
    r = client.post("/auth/login", json={"user": "pytest", "role": role})
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert "access_token" in data
    return data["access_token"]


def test_ingest_put_fetch_remove_flow():
    app = create_app()
    with app.test_client() as c:
        token = _auth_token(c, role="replicator")
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "topic": "doc",
            "text": "hello world",
            "embedding": [0.1, 0.2, 0.3],
            "tags": ["p2p", "crdt"],
            "ts": 1690000000,
        }

        # PUT
        r_put = c.post(
            "/ingest/crdt/put",
            headers=headers,
            json={"id": "doc:1", "payload": payload},
        )
        assert r_put.status_code == 200
        dp = r_put.get_json()
        assert dp["ok"] is True
        assert dp["id"] == "doc:1"
        assert "cid" in dp and isinstance(dp["cid"], str)
        assert "_cas" in dp["meta"]

        # FETH (without authorization allowed, optional)
        r_get = c.get("/ingest/crdt/fetch?id=doc:1")
        assert r_get.status_code == 200
        dg = r_get.get_json()
        assert dg["ok"] is True
        assert dg["result"]["data"]["text"] == "hello world"

        # REMOVE
        r_rem = c.delete("/ingest/crdt/rem", headers=headers, json={"id": "doc:1"})
        assert r_rem.status_code == 200
        dr = r_rem.get_json()
        assert dr["ok"] is True
