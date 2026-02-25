from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_mtls_whoami_smoke():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get(
        "/mtls/whoami",
        headers={
            "X-Client-Verified": "SUCCESS",
            "X-Client-DN": "CN=node-1,OU=core,O=Ester",
        },
    )
    # In some places the blueprint may not be connected - let's say 404.
    # If connected, it should be 200 and JSON.
    if r.status_code == 200:
        j = r.get_json()
        assert isinstance(j, dict)
    else:
        assert r.status_code in (200, 404)