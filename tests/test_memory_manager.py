# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytest

from cards_memory import CardsMemory
from memory_manager import MemoryManager
from structured_memory import StructuredMemory
from vector_store import VectorStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture
def memory_manager():
    vstore = VectorStore()
    structured_mem = StructuredMemory()
    cards = CardsMemory()
    return MemoryManager(vstore, structured_mem, cards)


def test_add_to_short_term(memory_manager):
    memory_manager.add_to_short_term("user1", "session1", {"msg": "test"})
    short = memory_manager.get_short_term("user1", "session1")
    assert len(short) == 1
    assert short[0]["msg"] == "test"


def test_add_to_medium_term(memory_manager):
    memory_manager.add_to_medium_term("user1", "q", "a", {"joy": 1.0}, ["test"])
    entries = memory_manager.medium_term.memory.get("user1", [])
    assert len(entries) == 1
    assert entries[0]["query"] == "q"


def test_add_to_long_term(memory_manager):
    memory_manager.add_to_long_term("long text")
    assert memory_manager.long_term.size > 0


def test_compact_short_to_medium(memory_manager):
    memory_manager.add_to_short_term("user1", "session1", {"msg": "msg1", "role": "user"})
    memory_manager.add_to_short_term("user1", "session1", {"msg": "msg2", "role": "assistant"})
    memory_manager.compact_short_to_medium()
    entries = memory_manager.medium_term.memory.get("user1", [])
    assert len(entries) == 1
    assert "msg1" in entries[0]["query"]


def test_gc_expired(memory_manager):
    # Simuliruem starye zapisi
    old_entry = {"timestamp": (datetime.now() - timedelta(days=100)).isoformat()}
    memory_manager.medium_term.memory["user1"] = [old_entry]
    memory_manager.gc_expired()
    assert len(memory_manager.medium_term.memory.get("user1", [])) == 0


def test_apply_decay(memory_manager):
    memory_manager.medium_term.memory["user1"] = [
        {"weight": 1.0, "timestamp": (datetime.now() - timedelta(days=1)).isoformat()}
    ]
    memory_manager.apply_decay("user1")
    entries = memory_manager.medium_term.memory.get("user1", [])
    assert entries[0]["weight"] < 1.0


def test_get_agenda(memory_manager):
    # Simuliruem offers
    memory_manager.record_offers(
        "user1",
        [
            {
                "id": "1",
                "title": "test",
                "status": "pending",
                "until": (datetime.now() + timedelta(days=1)).isoformat(),
            }
        ],
    )
    agenda = memory_manager.get_agenda("user1")
    assert len(agenda) == 1


def test_mark_offer(memory_manager):
    memory_manager.record_offers("user1", [{"id": "1", "status": "pending"}])
    memory_manager.mark_offer("user1", "1", "accepted")
    history = memory_manager.get_offers_history("user1")
    assert history[0]["status"] == "accepted"


def test_snooze_offer(memory_manager):
    memory_manager.record_offers("user1", [{"id": "1", "status": "pending"}])
    memory_manager.snooze_offer("user1", "1", 30)
    history = memory_manager.get_offers_history("user1")
    assert history[0]["status"] == "snoozed"


def test_get_offers_history(memory_manager):
    memory_manager.record_offers("user1", [{"timestamp": datetime.now().isoformat()}])
    hist = memory_manager.get_offers_history(
        "user1", (datetime.now() - timedelta(days=1)).isoformat()
    )
    assert len(hist) == 1


def test_heal_all(memory_manager):
    res = memory_manager.heal_all()
    assert isinstance(res, dict)
    assert "vstore_fixed" in res
    assert "mem_fixed" in res


def test_update_meta_memory(memory_manager):
    # Add some entries
    memory_manager.add_to_medium_term("user1", "q1", "a1", {"joy": 0.8}, ["tag"])
    memory_manager.add_to_medium_term("user1", "q2", "a2", {"anxiety": 0.2}, ["tag"])
    meta = memory_manager.update_meta_memory(days=1)
    assert "mood_avg" in meta
    assert meta["msgs_per_day"] > 0


def test_sample_rule_priority(memory_manager):
    rule = {"accepts": 5, "dismisses": 2}
    prio = memory_manager.sample_rule_priority(rule)
    assert 0 <= prio <= 1


def test_explain_offer(memory_manager):
    offer = {"reason": "test", "rule": "rule1"}
    memory_manager.record_offers("user1", [offer])
    explain = memory_manager.explain_offer(offer, "user1")
# assert "1 raz" in explain