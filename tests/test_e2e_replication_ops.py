from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def _h(dn: str):
    return {"X-Client-Verified": "SUCCESS", "X-Client-DN": dn}

def test_replication_allows_replicator():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/replication/test_snapshot", headers=_h("CN=node-1,OU=core,O=Ester"))
    assert r.status_code == 200
    assert r.get_json().get("type") == "snapshot"

def test_replication_blocks_ops():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/replication/test_snapshot", headers=_h("CN=ops-9,OU=ops,O=Ester"))
    assert r.status_code == 403

def test_ops_secure_ping_allows_ops():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/ops/secure_ping", headers=_h("CN=ops-2,OU=ops,O=Ester"))
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

def test_ops_secure_ping_blocks_node():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/ops/secure_ping", headers=_h("CN=node-2,OU=core,O=Ester"))
    assert r.status_code == 403