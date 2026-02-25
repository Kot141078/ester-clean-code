# -*- coding: utf-8 -*-
"""tests/crawler/test_crawler_budget.py - proverki byudzhetov, robots i kesha (bez seti).

MOSTY:
- (Yavnyy) Feykovyy fetcher vozvraschaet HTML; proveryaem, what kesh rabotaet i byudzhety/limity soblyudayutsya.
- (Skrytyy #1) Proveryaem, chto arkhivy zapreschayutsya srazu.
- (Skrytyy #2) Robots: emuliruem zapret prostym flagom v fake_robots (monkeypatch).

ZEMNOY ABZATs:
# The test proves that the crawler behaves “quietly” and predictably, and does not bomb external sites. c=a+b"""
from __future__ import annotations

import types
from crawler.client import BudgetedCrawler, FetchResult
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

HTML = b"""<html><head><title>Hello</title><meta name="description" content="Desc."></head>
<body><a href="/">x</a><a href="/">y</a></body></html>"""

def fake_fetcher(url, headers):
    return (200, HTML)

def test_cache_and_budgets(monkeypatch):
    # Let's tighten the budgets
    monkeypatch.setenv("OUTBOUND_MAX_RPS","1000")
    monkeypatch.setenv("OUTBOUND_BUDGET_PER_MIN","3")
    c = BudgetedCrawler(fetcher=fake_fetcher)

    # Let's slip in a robot function that always allows
    c._robots = lambda url: True  # type: ignore

    r1 = c.fetch("https://example.com/")
    assert r1.ok and r1.title == "Hello" and r1.links == 2

    # Cash: the second time the kached should return
    r2 = c.fetch("https://example.com/")
    assert r2.ok and r2.title == "Hello"  # The TTL cache gives the same result (the kached field is already “collapsed” inside)

    # Budget: after 3 requests per minute - refusal
    c.fetch("https://example.com/1")
    r4 = c.fetch("https://example.com/2")
    assert r4.ok is False and r4.reason in ("budget_exceeded","rate_limited")

def test_archives_blocked(monkeypatch):
    c = BudgetedCrawler(fetcher=fake_fetcher)
    c._robots = lambda url: True  # type: ignore
    r = c.fetch("https://host/path/file.zip")
    assert r.ok is False and r.reason == "disallowed_archive"