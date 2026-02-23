from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_providers_status_and_models(client, auth_header):
    r = client.get("/providers/status", headers=auth_header)
    assert r.status_code == 200
    st = r.get_json()
    assert "active" in st and "default_cloud" in st
    assert "lmstudio" in st

    r2 = client.get("/providers/models", headers=auth_header)
    assert r2.status_code == 200
    models = r2.get_json()["models"]
    assert isinstance(models, list) and len(models) >= 1


def test_providers_select(client, auth_header):
    r = client.post("/providers/select", json={"provider": "lmstudio"}, headers=auth_header)
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["active"] == "lmstudio"

    # neizvestnyy provayder
    r2 = client.post("/providers/select", json={"provider": "unknown"}, headers=auth_header)
    assert r2.status_code == 400
    j2 = r2.get_json()
# assert j2["ok"] is False