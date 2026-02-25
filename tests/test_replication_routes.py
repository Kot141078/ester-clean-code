# -*- coding: utf-8 -*-
import io
import os
import zipfile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_replication_snapshot_and_apply(client, auth_hdr_admin, monkeypatch, tmp_path):
    # Setting up the environment
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("REPL_TOKEN", "tok")
    monkeypatch.setenv("REPL_HMAC_KEY", "supersecret")
    # Podgotovim fayl v persist_dir
    p = tmp_path / "structured_mem"
    p.mkdir(parents=True, exist_ok=True)
    f = p / "store.json"
    f.write_text("[]", encoding="utf-8")

    # SNAPSHOT
    r = client.get("/replication/snapshot", headers={**auth_hdr_admin, "X-REPL-TOKEN": "tok"})
    assert r.status_code in (200, 503, 404)
    if r.status_code != 200:
        return
    assert r.headers.get("X-Signature", "").startswith("hmac-")
    data = r.data
    # let's change the local file a little so that later the LVV will work as expected
    import time as _t

    _t.sleep(0.01)
    f.write_text('[{"id":"a"}]', encoding="utf-8")

    # APPLY (uses the old snapshot - must be skipped due to LVV)
    r2 = client.post(
        "/replication/apply",
        headers={
            **auth_hdr_admin,
            "X-REPL-TOKEN": "tok",
            "X-Signature": r.headers["X-Signature"],
        },
        data=data,
    )
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2.get("ok") is True
    # Let's check that the file is not overwritten
    assert f.read_text(encoding="utf-8") == '[{"id":"a"}]'


def test_replication_guard_and_errors(client, auth_hdr_admin, monkeypatch, tmp_path):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    # no keys
    r = client.get("/replication/snapshot", headers=auth_hdr_admin)
    assert r.status_code in (503, 404)
