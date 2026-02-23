# -*- coding: utf-8 -*-
"""
tests/test_routes_mem_kg_api.py — dymovoy test API grafa znaniy (/mem/kg/*).
"""

from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_mem_kg_upsert_query_export(client, admin_jwt, monkeypatch, tmp_path):
    # Izoliruem khranilische
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))

    # upsert nodes
    r1 = client.post(
        "/mem/kg/upsert",
        json={
            "nodes": [
                {"id": "topic::ocr", "type": "topic", "label": "ocr"},
                {"id": "doc::1", "type": "artifact", "label": "invoice.pdf"},
            ]
        },
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert r1.status_code == 200, r1.data

    # upsert edges
    r2 = client.post(
        "/mem/kg/upsert",
        json={
            "edges": [
                {
                    "src": "topic::ocr",
                    "rel": "supports",
                    "dst": "doc::1",
                    "weight": 0.7,
                },
            ]
        },
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert r2.status_code == 200, r2.data

    # query nodes
    rq = client.get(
        "/mem/kg/query",
        query_string={"q": "ocr", "limit": 5},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert rq.status_code == 200
    jsq = rq.get_json()
    assert jsq["nodes"] and jsq["nodes"][0]["id"] == "topic::ocr"

    # neighbors
    rn = client.get(
        "/mem/kg/neighbors",
        query_string={"id": "topic::ocr"},
        headers={"Authorization": f"Bearer {admin_jwt}"},
    )
    assert rn.status_code == 200
    jsn = rn.get_json()
    assert jsn["node"]["id"] == "topic::ocr"
    assert jsn["out"] and jsn["out"][0]["dst"] == "doc::1"

    # export
    rexp = client.get("/mem/kg/export", headers={"Authorization": f"Bearer {admin_jwt}"})
    assert rexp.status_code == 200
    jse = rexp.get_json()
    assert any(n["id"] == "topic::ocr" for n in jse.get("nodes", []))
# assert any(e["dst"] == "doc::1" for e in jse.get("edges", []))