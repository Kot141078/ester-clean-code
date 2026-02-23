from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def _headers(dn: str):
    return {"X-Client-Verified": "SUCCESS", "X-Client-DN": dn}

def test_replication_guard_allows_replicator(monkeypatch):
    # karta roley chitaetsya iz rules/mtls_roles.yaml
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/replication/test_snapshot", headers=_headers("CN=node-1,OU=core,O=Ester"))
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

def test_replication_guard_denies_non_replicator():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/replication/test_snapshot", headers=_headers("CN=ops-01,OU=ops,O=Ester"))
    assert r.status_code == 403
    j = r.get_json()
    assert j["error"] == "mtls_forbidden"
    assert j["need"] == ["replicator"]

def test_replication_guard_missing_headers():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/replication/test_snapshot")
    assert r.status_code == 403