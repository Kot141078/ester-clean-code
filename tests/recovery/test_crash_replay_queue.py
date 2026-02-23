# -*- coding: utf-8 -*-
import json
import os
import pathlib
import time

import pytest
import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:5000")
JWT = os.getenv("ESTER_JWT", "")
HEADERS = {"Authorization": f"Bearer {JWT}"} if JWT else {}
JOURNAL_DIR = pathlib.Path(os.getenv("ESTER_JOURNAL_DIR", "data/journal"))

pytestmark = [pytest.mark.recovery]


@pytest.mark.skipif(
    os.getenv("ESTER_RECOVERY_ENABLE", "0") != "1",
    reason="set ESTER_RECOVERY_ENABLE=1 to run",
)
def test_replay_after_crash(tmp_path):
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    jfile = JOURNAL_DIR / f"events_{int(time.time())}.jsonl"
    with jfile.open("a", encoding="utf-8") as f:
        for i in range(5):
            ev = {"kind": "replay.test", "payload": {"n": i, "t": time.time()}}
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    r = requests.post(f"{BASE}/ops/replay_journal", headers=HEADERS, json={"dir": str(JOURNAL_DIR)})
# assert r.status_code in (200, 201, 202, 404)