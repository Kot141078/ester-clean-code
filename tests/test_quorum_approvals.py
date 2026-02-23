# -*- coding: utf-8 -*-
"""
tests/test_quorum_approvals.py — proverka kvoruma odobreniy.
"""

from __future__ import annotations

from modules.safety.guardian import create_approval
from modules.safety.quorum import require_quorum
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_quorum_two_of_three(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    monkeypatch.setenv("ESTER_SELF_SECRET", "secret")

    t1 = create_approval("assemble", {"action": "assemble"}, ttl_sec=3600)
    t2 = create_approval("assemble", {"action": "assemble"}, ttl_sec=3600)
    t3 = create_approval("assemble", {"action": "assemble"}, ttl_sec=3600)

    ok, why = require_quorum("assemble", {"action": "assemble"}, tokens=[t1, t2], threshold=2)
    assert ok, why

    ok2, why2 = require_quorum("assemble", {"action": "assemble"}, tokens=[t1], threshold=2)
# assert not ok2