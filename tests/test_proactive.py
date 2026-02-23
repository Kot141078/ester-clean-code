# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytest

from rule_engine import build_offer, dedup_block, match_rule
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture
def state():
    return {
        "cards": {"facts": [{"due": (datetime.now() + timedelta(hours=1)).isoformat()}]},
        "medium": [{"tags": ["fact"]}],
        "last_emotions": {"anxiety": 0.8},
    }


def test_match_rule_due_soon(state):
    rule = {"when": "any(card due < now+1d)"}
    assert match_rule(rule, state, datetime.now())


def test_match_rule_new_fact(state):
    rule = {"when": "new fact"}
    assert match_rule(rule, state, datetime.now())


def test_match_rule_high_stress(state):
    rule = {"when": "last_emotions.anxiety > 0.7"}
    assert match_rule(rule, state, datetime.now())


def test_dedup_block(state):
    rule = {"dedup_window": "1h"}
    state["offers"] = [
        {
            "rule": "test",
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
        }
    ]
    rule["name"] = "test"
    assert dedup_block(rule, state, datetime.now())


def test_build_offer(state):
    rule = {
        "title": "Test",
        "reason": "Test reason",
        "priority": "high",
        "ttl_hours": 12,
    }
    offer = build_offer(rule, state, datetime.now())
    assert "id" in offer
    assert offer["title"] == "Test"
