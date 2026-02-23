# -*- coding: utf-8 -*-
import os

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

pytestmark = [pytest.mark.recovery]

ART_DIR = "artifacts/recovery"
FILES = ["1_run.json", "2_verify.json", "4_restore.json"]


@pytest.mark.skipif(
    os.getenv("ESTER_RECOVERY_FILES", "0") != "1",
    reason="set ESTER_RECOVERY_FILES=1 to run",
)
def test_recovery_files_present():
    assert os.path.isdir(ART_DIR), f"{ART_DIR} not found"
    missing = [f for f in FILES if not os.path.exists(os.path.join(ART_DIR, f))]
    assert (
        not missing
), f"missing: {missing}. Run 'make recovery' or 'bash scripts/recovery_drill.sh'"