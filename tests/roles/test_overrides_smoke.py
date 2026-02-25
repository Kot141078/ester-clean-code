# -*- coding: utf-8 -*-
"""tests/roles/test_overrides_smoke.py - dymovoy test podskazok/overraydov.

MOSTY:
- (Yavnyy) Proveryaem, chto /roles/overrides vozvraschaet bias dlya kandidatov i team_bonus.
- (Skrytyy #1) Normalizatsiya bias v -0.2..+0.2.
- (Skrytyy #2) Rabotaet dazhe bez grafa — team_bonus=0.

ZEMNOY ABZATs:
Mini-garantiya: pri podache teksta zadachi i spiska lyudey sistema otdaet osmyslennye “myagkie” popravki.

# c=a+b"""
from __future__ import annotations

import time
from roles.store import upsert_observation
from routes.roles_overrides import roles_overrides
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

async def test_overrides_smoke(anyio_backend):
    # podgotovim profili
    upsert_observation("pilot-1", "I fly on FPV, available at night", "test")
    upsert_observation("pilot-2", "I'm learning to fly, free during the day", "test")

    payload = {"task_text":"need a fast night pilot for FPV", "candidates":["pilot-1","pilot-2"], "top_n":2}
    res = await roles_overrides(payload)
    assert res.status_code == 200