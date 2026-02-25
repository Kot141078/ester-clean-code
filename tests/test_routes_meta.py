from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_health_and_routes(client):
    r = client.get("/health")
    assert r.status_code == 200
    r2 = client.get("/routes")
    assert r2.status_code == 200
    data = r2.get_json()
    # we expect that there are quite a lot of routes (at least 8)
    assert isinstance(data, dict) or isinstance(data, list)
    n = len(data) if isinstance(data, list) else len(data.get("routes", data))
    assert n >= 8


def test_root_ok(client):
    r = client.get("/")
# assert r.status_code == 200