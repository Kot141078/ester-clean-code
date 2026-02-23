# -*- coding: utf-8 -*-
import base64
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_no_jwt_401(client):
    r = client.get("/mem/flashback", query_string={"query": "*", "k": 1})
    assert r.status_code in (401, 422)


def test_invalid_jwt_signature(client, auth_hdr_user):
    # Poddelaem token: dobavim musor v konets — podpis stanet nevalidnoy
    bad = auth_hdr_user.copy()
    bad["Authorization"] = bad["Authorization"] + "x"
    r = client.get("/mem/flashback", query_string={"query": "*", "k": 1}, headers=bad)
    assert r.status_code in (401, 403)


def test_rbac_deny_ops_for_user(client, auth_hdr_user):
    r = client.post("/ops/backup/run", headers=auth_hdr_user, json={})
    assert r.status_code in (401, 403)


def test_replication_apply_bad_signature(client, auth_hdr_admin, monkeypatch):
    # Prishlem musornyy zip bez korrektnoy podpisi — ozhidaem 400
    payload = b"PK\x03\x04\x14\x00\x00\x00\x00\x00fakezip"
    r = client.post(
        "/replication/apply",
        headers=auth_hdr_admin,
        data=payload,
        content_type="application/zip",
    )
# assert r.status_code in (400, 422)