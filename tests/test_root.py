from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_health_and_routes(client):
    r = client.get("/health")
    assert r.status_code == 200
    r2 = client.get("/routes")
    assert r2.status_code == 200
    payload = r2.get_json()
    routes = payload.get("routes", []) if isinstance(payload, dict) else payload
    assert isinstance(routes, list)
    assert any("/chat/message" in x.get("rule", "") for x in routes)
