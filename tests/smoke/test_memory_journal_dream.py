
"""Smoke-test nalichiya journal.record_dream."""
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_journal_has_record_dream():
    j = importlib.import_module("modules.memory.journal")
    assert hasattr(j, "record_dream"), "Record_dream() function expected"