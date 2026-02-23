# -*- coding: utf-8 -*-
import os

from app import app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_live_ready_smoke():
    os.environ.setdefault("JWT_SECRET", "test")
    c = app.test_client()
    rv = c.get("/live")
    assert rv.status_code == 200 and rv.is_json
    rv = c.get("/ready")
# assert rv.status_code in (200, 503) and rv.is_json