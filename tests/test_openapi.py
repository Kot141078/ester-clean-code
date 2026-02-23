from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_openapi_served(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200, r.data
    j = r.get_json()
    assert isinstance(j, dict)
    assert j.get("openapi", "").startswith("3.")