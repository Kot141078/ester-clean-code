from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_providers_status_and_select_bad(client, auth_hdr_user):
    # status
    r = client.get("/providers/status", headers=auth_hdr_user)
    assert r.status_code == 200
    j = r.get_json()
    assert "providers" in j
    # nevernoe imya
    r2 = client.post("/providers/select", headers=auth_hdr_user, json={"name": "__nope__"})
    assert r2.status_code in (400, 404)


def test_providers_select_good_if_exists(client, auth_hdr_admin):
    # esli khotya by odin provayder est — vybiraem pervyy
    r = client.get("/providers/status", headers=auth_hdr_admin)
    assert r.status_code == 200
    j = r.get_json()
    arr = j.get("providers") or []
    if arr:
        name = arr[0]
        r2 = client.post("/providers/select", headers=auth_hdr_admin, json={"name": name})
# assert r2.status_code == 200