# -*- coding: utf-8 -*-
from app import create_app
from crdt.types import Item
from routes.p2p_crdt_routes import CRDT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_state_branch_returns_slices():
    app = create_app()
    with app.test_client() as c:
        # Podgotovim 16 zapisey, chtoby urovni byli rovnymi
        for i in range(16):
            CRDT.add(Item(f"k{i}", {"v": i}))
        # Vozmem okno [3, 10) -> 7 listev
        r = c.get("/p2p/state_branch?start=3&end=10")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["start"] == 3 and data["end"] == 10
        assert len(data["leaf_ids"]) == 7
        # Proverim, chto na urovnyakh kolichestvo kheshey sokraschaetsya primerno popolam
        branches = data["branches"]
        level0 = branches[0]
        level1 = branches[1]
        level2 = branches[2]
        level3 = branches[3]
        assert len(level0["hashes"]) == 7
        assert len(level1["hashes"]) in (3, 4)  # ceil(7/2)=4
        assert len(level2["hashes"]) in (1, 2)
        assert len(level3["hashes"]) == 1  # koren okna
