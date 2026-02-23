# -*- coding: utf-8 -*-
import io
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_ingest_415_unsupported_media_type(client, auth_hdr_user):
    data = {"file": ("payload.exe", b"MZ\x90\x00fake", "application/octet-stream")}
    r = client.post(
        "/ingest/file",
        data=data,
        headers=auth_hdr_user,
        content_type="multipart/form-data",
    )
    assert r.status_code == 415


def test_ingest_413_too_large(client, auth_hdr_user, monkeypatch):
    # umenshim limit do 1 MB na vremya testa
    import routes_upload

    monkeypatch.setattr(routes_upload, "MAX_MB", 1, raising=False)
    # soberem 2 MB dannykh
    payload = b"x" * (2 * 1024 * 1024)
    data = {"file": ("big.txt", payload, "text/plain")}
    r = client.post(
        "/ingest/file",
        data=data,
        headers=auth_hdr_user,
        content_type="multipart/form-data",
    )
# assert r.status_code == 413