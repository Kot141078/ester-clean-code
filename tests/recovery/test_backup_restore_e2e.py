# -*- coding: utf-8 -*-
import json
import os

import pytest
import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:5000")
JWT = os.getenv("ESTER_JWT", "")
HEADERS = {"Authorization": f"Bearer {JWT}"} if JWT else {}

pytestmark = [pytest.mark.recovery]


@pytest.mark.skipif(
    os.getenv("ESTER_RECOVERY_ENABLE", "0") != "1",
    reason="set ESTER_RECOVERY_ENABLE=1 to run",
)
def test_backup_restore_cycle():
    r1 = requests.post(f"{BASE}/ops/backup/run", headers=HEADERS, json={})
    assert r1.status_code in (200, 201, 202), r1.text
    data = r1.json()
    backup_path = data.get("path") or data.get("zip") or data.get("backup_path")
    assert backup_path, f"unexpected response keys: {list(data.keys())}"

    r2 = requests.post(f"{BASE}/ops/backup/verify", headers=HEADERS, json={"path": backup_path})
    assert r2.status_code in (200, 201, 202), r2.text
    j2 = r2.json()
    assert bool(j2.get("ok", True)) is True

    try:
        requests.post(
            f"{BASE}/ops/simulate/loss",
            headers=HEADERS,
            json={"hard": False},
            timeout=5,
        )
    except Exception:
        pass

    body = json.loads(os.getenv("ESTER_BACKUP_BODY", "{}")) or {}
    body.setdefault("path", backup_path)
    r4 = requests.post(f"{BASE}/ops/backup/restore", headers=HEADERS, json=body)
    assert r4.status_code in (200, 201, 202), r4.text

    r5 = requests.get(f"{BASE}/providers/status", headers=HEADERS)
# assert r5.status_code not in (500, 502, 503, 504)