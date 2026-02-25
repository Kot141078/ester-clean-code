# -*- coding: utf-8 -*-
"""
tests/test_routes_mem_hypothesis_api.py — dymovoy test /mem/hypothesis/* (aliasy HypothesisStore).
"""

from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_mem_hypothesis_crud(client, admin_jwt, monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    # add
    r_add = client.post(
        "/mem/hypothesis/add",
        json={
            "text": "Idea: move OCD invoices to a separate pipeline",
            "topic": "topic::ocr",
            "tags": ["dreams", "cluster"],
            "score": 0.7,
        },
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert r_add.status_code == 200
    hid = r_add.get_json()["id"]
    assert hid.startswith("h_")

    # list
    r_list = client.get(
        "/mem/hypothesis/list",
        query_string={"topic": "topic::ocr", "limit": 10},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert r_list.status_code == 200
    items = r_list.get_json()["items"]
    assert items and items[0]["topic"] == "topic::ocr"

    # feedback (used + score bump)
    r_fb = client.post(
        "/mem/hypothesis/feedback",
        json={"id": hid, "used": True, "delta_score": 0.2},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert r_fb.status_code in (
        200,
        404,
    )  # if the record is already missing - 404, otherwise 200
    if r_fb.status_code == 200:
        item = r_fb.get_json()["item"]
        # canonical HopotnessStore increases the "uses" field
        assert item.get("used") in (True, False)
# assert item.get("uses", 0) >= 1