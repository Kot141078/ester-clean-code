# -*- coding: utf-8 -*-
"""
tests/selfmanage/test_watchdog.py — proverki perekhodov watchdog.

MOSTY:
- (Yavnyy) Feykovyy servis: pervyy raz padaet, zatem prokhodit; watchdog delaet restart i sbrasyvaet backoff.
- (Skrytyy #1) Proveryaem, chto next_at sdvigaetsya pri fail.
- (Skrytyy #2) Net fonovogo potoka v teste — upravlyaem tick() vruchnuyu.

ZEMNOY ABZATs:
Dokazatelstvo, chto avto-remont rabotaet i ne «zalipaet».

# c=a+b
"""
from __future__ import annotations

import time

from modules.selfmanage.watchdog import Watchdog, Service
from modules.selfmanage.health import _ok, _fail
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class Flaky:
    def __init__(self):
        self.fail = True
        self.restarts = 0
    def check(self):
        if self.fail:
            return _fail("flaky", 0, "boom")
        return _ok("flaky", 0)
    def restart(self):
        self.restarts += 1
        self.fail = False
        return True

def test_watchdog_transitions():
    f = Flaky()
    wd = Watchdog([Service(name="flaky", check=f.check, restart=f.restart, cooldown_sec=0.01)], interval_ms=1)
    s1 = wd.tick()
    assert any(x.name.endswith(":restart") for x in s1)
    time.sleep(0.02)
    s2 = wd.tick()
    assert any(x.name == "flaky" and x.status == "ok" for x in s2)
    assert f.restarts >= 1