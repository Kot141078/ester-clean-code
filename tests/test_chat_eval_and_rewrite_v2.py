# -*- coding: utf-8 -*-
"""Tests for self-eval and deterministic rewrite."""

from modules.chat_eval import self_eval
from modules.chat_rewrite import rewrite


def test_eval_basic_scores():
    txt = "Firstly, the system starts up quickly. However, the structure needs to be improved."
    res = self_eval(txt)
    assert res["scores"]["clarity"] > 0.6
    assert res["scores"]["logic"] > 0.6
    assert res["scores"]["toxicity"] >= 0.9
    assert 0 <= res["scores"]["overall"] <= 1


def test_rewrite_improves_and_keeps_code():
    src = """This is bad!!! First of all, everything is very very long and repetitive.

yoyopothon
def f(s): # don't touch
    return s*2
yoyo"""
    rewritten = rewrite(src)
    eval_before = self_eval(src)["scores"]["overall"]
    eval_after = self_eval(rewritten)["scores"]["overall"]

    assert "```python" in rewritten
    assert "def f(x):" in rewritten
    assert "return x*2" in rewritten
    assert eval_after >= eval_before
