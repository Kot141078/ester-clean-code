# -*- coding: utf-8 -*-
"""
tests/messaging/test_style_router.py — marshrutizatsiya stilya i render.

MOSTY:
- (Yavnyy) Proveryaem vybor lawyer/student/friend/neutral i A/B-pereklyuchenie.
- (Skrytyy #1) Bez LLM-bekenda: off → no-op.
- (Skrytyy #2) Stels-persona vliyaet na nalichie «pozhaluysta» (dlya direct).

ZEMNOY ABZATs:
Garantiruet, chto soobscheniya zvuchat umestno adresatu, a pereklyuchateli rabotayut mgnovenno.

# c=a+b
"""
from __future__ import annotations

import os

from nl.authoring_router import author_text
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_styles_basic(monkeypatch):
    monkeypatch.setenv("AUTHORING_STYLE_AB","A")
    t1 = author_text("nuzhno prodlit srok sdachi", recipient_kind="lawyer")
    t2 = author_text("obyasni zakon sokhraneniya energii", recipient_kind="student")
    t3 = author_text("pozdrav s DR", recipient_kind="friend")
    t4 = author_text("vstrecha v 16:00", recipient_kind="neutral")
    assert "riskov" in t1.lower() or "shag" in t1.lower()
    assert "primer" in t2.lower() or "uprazhnenie" in t2.lower()
    assert "🙌" in t3 or "dobr" in t3.lower()
    assert "vstrecha" in t4.lower()

def test_persona_direct(monkeypatch):
    monkeypatch.setenv("AUTHORING_STYLE_AB","B")
    monkeypatch.setenv("MSG_STEALTH_PERSONA","direct")
    t = author_text("pozhaluysta utochni detali", recipient_kind="neutral")
    assert "pozhaluysta" not in t.lower()