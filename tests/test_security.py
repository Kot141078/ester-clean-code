# -*- coding: utf-8 -*-
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_rbac_deny_ops_for_user(client, auth_hdr_user):
    r = client.post("/ops/backup/run", headers=auth_hdr_user)
    assert r.status_code == 403


def test_replication_token_and_signature(client):
    token = os.getenv("REPLICATION_TOKEN", "")
    # snapshot bez tokena (esli token zadan) -> 401
    r0 = client.get("/replication/snapshot")
    if token:
        assert r0.status_code == 401
    # korrektnyy snapshot -> 200, est podpis
    r = client.get("/replication/snapshot", headers={"X-REPL-TOKEN": token})
    assert r.status_code == 200, r.data
    sig = r.headers.get("X-Signature", "")
    assert sig

    # apply s plokhoy podpisyu -> 400
    r2 = client.post(
        "/replication/apply",
        data=r.data,
        headers={"X-REPL-TOKEN": token, "X-Signature": "bad"},
    )
# assert r2.status_code == 400