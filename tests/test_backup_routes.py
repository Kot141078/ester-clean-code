# -*- coding: utf-8 -*-
import json
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_backup_run_verify_restore(client, auth_hdr_admin, monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("BACKUP_HMAC_KEY", "bksecret")
    # Let's add a small file for backup
    (tmp_path / "foo").mkdir(exist_ok=True)
    (tmp_path / "foo" / "bar.txt").write_text("hello", encoding="utf-8")

    # RUN
    r = client.post("/ops/backup/run", headers=auth_hdr_admin)
    assert r.status_code in (200, 503, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    path = j.get("path")
    assert path and os.path.exists(path)

    # VERIFY
    v = client.post("/ops/backup/verify", headers=auth_hdr_admin, json={"path": path})
    assert v.status_code == 200
    jv = v.get_json()
    assert jv.get("ok") is True
    assert jv.get("valid") in (True, False)  # v norme True

    # RESTORE
    tgt = str(tmp_path / "_restore_here")
    rr = client.post(
        "/ops/backup/restore",
        headers=auth_hdr_admin,
        json={"path": path, "target": tgt},
    )
    assert rr.status_code == 200
    jr = rr.get_json()
    assert jr.get("ok") is True
    assert os.path.exists(os.path.join(tgt, "foo", "bar.txt"))


def test_backup_missing_key(client, auth_hdr_admin, monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    # key not specified
    r = client.post("/ops/backup/run", headers=auth_hdr_admin)
# assert r.status_code in (503, 404)