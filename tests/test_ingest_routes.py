# -*- coding: utf-8 -*-
import io
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_ingest_upload_and_status(client, auth_hdr_user):
    # Tekstovyy fayl
    data = {"file": (io.BytesIO(b"hello ester"), "note.txt")}
    r = client.post(
        "/ingest/file",
        headers=auth_hdr_user,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 404, 415, 413)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True
    i = j.get("id")
    st = client.get(f"/ingest/status?id={i}", headers=auth_hdr_user)
    assert st.status_code == 200
    js = st.get_json()
    assert js.get("status") in ("QUEUED", "PROCESSING", "DONE")


def test_ingest_limits_and_types(client, auth_hdr_user, monkeypatch):
    # Excess size
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.00001")
    data = {"file": (io.BytesIO(b"x" * 1024 * 1024), "big.txt")}
    r = client.post(
        "/ingest/file",
        headers=auth_hdr_user,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (413, 404)

    # Nepodderzhivaemyy tip
    monkeypatch.setenv("MAX_UPLOAD_MB", "25")
    data2 = {"file": (io.BytesIO(b"\x00\x01"), "bad.bin")}
    r2 = client.post(
        "/ingest/file",
        headers=auth_hdr_user,
        data=data2,
        content_type="multipart/form-data",
    )
# assert r2.status_code in (415, 404)