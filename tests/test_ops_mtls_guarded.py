from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def _h(dn: str):
    return {"X-Client-Verified": "SUCCESS", "X-Client-DN": dn}

def test_ops_guard_allows_ops():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/ops/secure_ping", headers=_h("CN=ops-1,OU=ops,O=Ester"))
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

def test_ops_guard_denies_non_ops():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/ops/secure_ping", headers=_h("CN=node-1,OU=core,O=Ester"))
    assert r.status_code == 403
    j = r.get_json()
    assert j["error"] == "mtls_forbidden"
    assert j["need"] == ["ops"]

def test_ops_guard_missing_headers():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/ops/secure_ping")
    assert r.status_code == 403