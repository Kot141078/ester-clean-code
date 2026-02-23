from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_providers_status_and_select(client, auth_hdr_user, auth_hdr_admin):
    # status
    r = client.get("/providers/status", headers=auth_hdr_user)
    assert r.status_code == 200, r.data
    j = r.get_json()
    assert "active" in j and "available" in j

    # select valid
    r2 = client.post("/providers/select", json={"mode": "local"}, headers=auth_hdr_admin)
    assert r2.status_code == 200, r2.data
    j2 = r2.get_json()
    assert j2.get("active") == "local"

    # select invalid
    r3 = client.post("/providers/select", json={"mode": "nope"}, headers=auth_hdr_admin)
    assert r3.status_code == 400