# -*- coding: utf-8 -*-
import os

from modules.ingest.cas import get_path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_adapter_installed_and_put(tmp_path, monkeypatch):
    # izolyatsiya CAS
    monkeypatch.setenv("ESTER_CAS_DIR", str(tmp_path / "cas"))

    from app import app as flask_app
    adapter = flask_app.extensions.get("vector_crdt_adapter")
    assert adapter is not None, "vector_crdt_adapter not installed"

    payload = b"Hello, Ester!"
    meta = {"kind": "doc", "name": "hello.txt"}
    crdt = adapter.put(meta=meta, payload_bytes=payload, embedding=[0.1, 0.2, 0.3])  # type: ignore

    assert isinstance(crdt, dict)
    assert crdt["meta"]["name"] == "hello.txt"
    assert crdt["cas"].startswith("sha256:")
    assert crdt["size"] == len(payload)
    assert crdt["embedding_ref"] and str(crdt["embedding_ref"]).startswith("sha256:")

    # fayl realno lezhit v CAS
    p_payload = get_path(crdt["cas"])
    assert os.path.exists(p_payload)