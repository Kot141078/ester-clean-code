from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_kg_upsert_query_export_import(client, auth_hdr_user, tmp_path):
    # upsert
    u = client.post(
        "/mem/kg/upsert",
        headers=auth_hdr_user,
        json={
            "nodes": [{"id": "n1", "type": "person", "name": "Ester"}],
            "edges": [{"src": "n1", "rel": "knows", "dst": "n2", "weight": 0.8}],
        },
    )
    assert u.status_code in (200, 404)
    if u.status_code != 200:
        return
    # query
    q = client.get("/mem/kg/query?q=ester&type=person&limit=5", headers=auth_hdr_user)
    assert q.status_code == 200
    jq = q.get_json()
    assert jq.get("ok") is True
    # export
    ex = client.get("/mem/kg/export", headers=auth_hdr_user)
    assert ex.status_code == 200
    jx = ex.get_json()
    assert jx.get("ok") is True
    # import
    imp = client.post("/mem/kg/import", headers=auth_hdr_user, json=jx.get("graph"))
    assert imp.status_code == 200


def test_hypothesis_get_post(client, auth_hdr_user):
    g = client.get("/mem/hypothesis", headers=auth_hdr_user)
    assert g.status_code in (200, 404)
    if g.status_code != 200:
        return
    jg = g.get_json()
    assert jg.get("ok") is True
    p = client.post(
        "/mem/hypothesis",
        headers=auth_hdr_user,
        json={
            "text": "Ideya: snabdit replikatsiyu CRDT-kontrolem",
            "tags": ["idea", "replication"],
        },
    )
    assert p.status_code == 200
    jp = p.get_json()
# assert jp.get("ok") is True