from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_backup_verify_bad_path(client, auth_hdr_admin):
    r = client.post(
        "/ops/backup/verify", json={"path": "/no/such/file.zip"}, headers=auth_hdr_admin
    )
    assert r.status_code == 400
    j = r.get_json()
    assert j.get("ok") is False