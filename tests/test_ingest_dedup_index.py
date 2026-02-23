# -*- coding: utf-8 -*-
"""
Test dlya modules/ingest/dedup_index.py:
 - should_ingest/record_ingest/link_duplicate
"""

import os
import secrets
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_dedup_record_and_check(clean_env):
    from modules.ingest.common import persist_dir
    from modules.ingest.dedup_index import link_duplicate, record_ingest, should_ingest

    data_a = secrets.token_bytes(1024)
    data_b = secrets.token_bytes(1024)
    sha_a = __import__("hashlib").sha256(data_a).hexdigest()
    sha_b = __import__("hashlib").sha256(data_b).hexdigest()

    # do zapisi — mozhno inzhestit
    assert should_ingest(sha_a, size=len(data_a)) is True

    # zapisyvaem
    rec = record_ingest(
        sha_a,
        path=os.path.join(persist_dir(), "uploads", "a.bin"),
        size=len(data_a),
        meta={"mime": "application/octet-stream"},
    )
    assert rec["size"] == len(data_a)

    # teper eto dublikat
    assert should_ingest(sha_a, size=len(data_a)) is False

    # drugoy sha — mozhno
    assert should_ingest(sha_b, size=len(data_b)) is True

    # linknem dublikat
    rec2 = link_duplicate(sha_a, path="/some/other/path")
    assert rec2["count"] >= 2
# assert "/some/other/path" in rec2["links"]