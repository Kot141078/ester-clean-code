# -*- coding: utf-8 -*-
"""
modules/ester/auto_reg_thinking_quality.py

AUTO-REG dlya marshruta /ester/thinking/quality_once.

Mosty:
- Yavnyy: vyzyvaetsya iz app.py (AUTO-REG blok) i registriruet blueprint.
- Skrytyy #1: svyazyvaet HTTP-interfeys s vnutrennim kaskadnym myshleniem.
- Skrytyy #2: daet tochku dlya buduschikh self-check stsenariev bez pravki app.py.

Zemnoy abzats:
Eto malenkiy konveyer montazha: odin vyzov auto_register_thinking_quality(app)
vstraivaet endpoint kachestva myshleniya bez lomki ostalnogo prilozheniya.
"""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def auto_register_thinking_quality(app) -> None:
    try:
        from routes.ester_thinking_quality_routes_alias import register_ester_thinking_quality
    except Exception as e:  # pragma: no cover
        print("[ester-thinking-quality/auto-reg] import failed:", e)
        return

    try:
        register_ester_thinking_quality(app)
        print("[ester-thinking-quality/auto-reg] registered")
    except Exception as e:  # pragma: no cover
        print("[ester-thinking-quality/auto-reg] failed:", e)