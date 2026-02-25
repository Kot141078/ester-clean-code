# -*- coding: utf-8 -*-
import os

from app import app  # type: ignore
from tools.rbac_audit import main as rbac_main
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_rbac_audit_passes(tmp_path):
    # If desired, you can replace the matrix via ENV/temporary file
    rc = rbac_main(app)
    assert rc == 0
