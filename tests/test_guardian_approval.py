# -*- coding: utf-8 -*-
import time

from modules.safety.guardian import create_approval, validate_approval
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_approval_smoke():
    rec = create_approval("backup.run", ttl_sec=5)
    assert rec["ok"] is True
    tok = rec["token"]
    assert validate_approval(tok, "backup.run", max_age_sec=5) is True

def test_approval_wrong_action():
    rec = create_approval("ops.restore", ttl_sec=5)
    tok = rec["token"]
    assert validate_approval(tok, "backup.run", max_age_sec=5) is False

def test_approval_expired():
    rec = create_approval("danger.op", ttl_sec=1)
    tok = rec["token"]
    # podozhdat > ttl
    time.sleep(1.2)
    assert validate_approval(tok, "danger.op") is False