# -*- coding: utf-8 -*-
"""
tests/messaging/test_wa_templates_preview.py — predprosmotr WA shablonov.

MOSTY:
- (Yavnyy) preview_template renderit body s podstanovkoy {{1}}, {{2}}, ...
- (Skrytyy #1) Otsutstvuyuschiy shablon → None; bez body → None.
- (Skrytyy #2) Lishnie peremennye bezopasno ignoriruyutsya.

ZEMNOY ABZATs:
Zaschitnyy «dymovoy» test — chtoby predprosmotr ne lomalsya i pokazyval deystvitelno to, chto uydet po smyslu.

# c=a+b
"""
from __future__ import annotations

import os
from pathlib import Path

from messaging.wa_templates import preview_template, list_templates
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_preview(monkeypatch, tmp_path: Path):
    cfg = tmp_path/"wa_templates.yaml"
    cfg.write_text(
        "templates:\n"
        "  x:\n"
        "    lang: ru\n"
        "    namespace: ns\n"
        "    body: \"A {{1}} B {{2}} C\"\n"
        "    variables: [v1, v2]\n", encoding="utf-8")
    monkeypatch.setenv("WA_TEMPLATES_CONFIG", str(cfg))
    t = preview_template("x", ["Q","W"])
    assert t == "A Q B W C"
    t2 = preview_template("x", ["ONLY"])
    assert t2 == "A ONLY B {{2}} C"
    assert preview_template("y", ["1"]) is None