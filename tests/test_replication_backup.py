# -*- coding: utf-8 -*-
import os

from security.signing import hmac_verify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_replication_snapshot_apply(client):
    token = os.getenv("REPLICATION_TOKEN", "")
    # snapshot
    r = client.get("/replication/snapshot", headers={"X-REPL-TOKEN": token})
    assert r.status_code == 200, r.data
    blob = r.data
    sig = r.headers.get("X-Signature") or ""
    assert sig and hmac_verify(blob, sig)

    # apply
    r2 = client.post(
        "/replication/apply",
        data=blob,
        headers={"X-REPL-TOKEN": token, "X-Signature": sig},
    )
    assert r2.status_code == 200, r2.data


def test_backup_run_verify_restore(client, auth_hdr_operator, auth_hdr_admin):
    # run
    r = client.post("/ops/backup/run", headers=auth_hdr_operator)
    assert r.status_code == 200, r.data
    j = r.get_json()
    zip_path = j.get("zip")
    assert zip_path and os.path.isfile(zip_path)

    # verify
    r2 = client.post("/ops/backup/verify", json={"path": zip_path}, headers=auth_hdr_admin)
    assert r2.status_code == 200
    assert r2.get_json().get("ok") is True

    # restore (temporary folder)
    tmp_dir = os.path.join(os.path.dirname(zip_path), "restore_tmp")
    r3 = client.post(
        "/ops/backup/restore",
        json={"path": zip_path, "target_dir": tmp_dir},
        headers=auth_hdr_admin,
    )
    assert r3.status_code == 200, r3.data


def test_backup_rbac_deny_for_user(client, auth_hdr_user):
    r = client.post("/ops/backup/run", headers=auth_hdr_user)
    assert r.status_code == 403
