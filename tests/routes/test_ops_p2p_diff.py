# -*- coding: utf-8 -*-
import json

from app import create_app
from crdt.types import Item
from routes.p2p_crdt_routes import CRDT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _auth_token(client, role="replicator"):
    r = client.post("/auth/login", json={"user": "pytest", "role": role})
    assert r.status_code in (200, 201)
    return r.get_json()["access_token"]


def test_diff_json_simulation_no_network():
    app = create_app()
    with app.test_client() as c:
        # Dobavim paru zapisey lokalno
        CRDT.add(Item("alpha", {"t": 1}))
        CRDT.add(Item("beta", {"t": 2}))

        # Poluchim lokalnoe sostoyanie /p2p/state level=0
        r_state = c.get("/p2p/state?level=0")
        assert r_state.status_code == 200
        st = r_state.get_json()
        leaf_ids = st["leaf_ids"]
        leaf_hashes = st["level"]

        # Sravnivaem lokalnoe s lokalnym -> diff pustoy
        r_diff = c.post(
            "/ops/p2p/diff/json",
            json={"leaf_ids": leaf_ids, "leaf_hashes": leaf_hashes},
        )
        assert r_diff.status_code == 200
        dj = r_diff.get_json()
        assert dj["ok"] is True
        assert dj["diff_ids"] == []

        # Menyaem odnu zapis lokalno, no peredaem starye kheshi — teper dolzhen poyavitsya diff
        CRDT.add(Item("beta", {"t": 3}))
        r_diff2 = c.post(
            "/ops/p2p/diff/json",
            json={"leaf_ids": leaf_ids, "leaf_hashes": leaf_hashes},
        )
        assert r_diff2.status_code == 200
        d2 = r_diff2.get_json()
        assert "beta" in d2["diff_ids"]
