# -*- coding: utf-8 -*-
import os

from modules.ingest.cas import put_bytes
from tools.merkle_cas import merkle_root
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_cas_dedup_and_merkle(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_CAS_DIR", str(tmp_path / "cas"))

    d1, p1, s1 = put_bytes(b"same-payload")
    d2, p2, s2 = put_bytes(b"same-payload")  # tot zhe digest
    assert d1 == d2
    assert os.path.exists(p1)
    assert os.path.exists(p2)  # this is the same file
    assert s1 == s2 == len(b"same-payload")

    root = merkle_root([d1, d2])
    # with duplicate leaves the root is determined
    assert isinstance(root, str) and len(root) == 64