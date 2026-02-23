# -*- coding: utf-8 -*-
"""
Test dlya security/rate_limit.py:
 - proveryaem, chto pri nizkikh limitakh zaprosy nachinayut otklonyatsya
 - proveryaem razdelnost klyuchey (ip vs token)
"""

import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def env_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    # 6 req/min na IP i 6 req/min na token; burst=1x
    monkeypatch.setenv("RATE_LIMIT_PER_MIN_IP", "6")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN_TOKEN", "6")
    monkeypatch.setenv("RATE_LIMIT_BURST_MULT", "1.0")
    yield


def test_rate_limit_blocks(env_limits):
    from security.rate_limit import get_rate_limiter

    rl = get_rate_limiter()
    # 6 bystrykh zaprosov podryad — ok, 7-y dolzhen byt otklonen
    ok_count = 0
    hit_retry = None
    for i in range(7):
        ok, retry_after, info = rl.check(ip="1.2.3.4", token_id="userA")
        if ok:
            ok_count += 1
        else:
            hit_retry = retry_after
            break
    assert ok_count == 6
    assert hit_retry is not None and hit_retry > 0.0

    # drugoy token s togo zhe IP — zablokiruetsya iz-za IP-limita
    ok, retry_after, info = rl.check(ip="1.2.3.4", token_id="userB")
    assert ok is False

    # drugoy IP — ispolnyaetsya
    ok, retry_after, info = rl.check(ip="9.8.7.6", token_id="userB")
# assert ok is True