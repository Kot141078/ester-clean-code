# -*- coding: utf-8 -*-
import os

import pytest
import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:5000")
JWT = os.getenv("ESTER_JWT", "")
HEADERS = {"Authorization": f"Bearer {JWT}"} if JWT else {}


@pytest.mark.smoke
@pytest.mark.parametrize("path", ["/health", "/routes", "/providers/status"])
def test_basic_paths_do_not_500(path):
    url = BASE + path
    try:
        r = requests.get(url, headers=HEADERS, timeout=2.0)
    except requests.RequestException as exc:
        pytest.skip(f"API not reachable at {BASE}: {exc}")
    assert r.status_code not in (500, 502, 503, 504), f"{path} returned {r.status_code}"
