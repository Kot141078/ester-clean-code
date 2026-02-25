
"""Stoke test of the day's narrative summary."""
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_daily_narrative_helper_exists_and_works():
    m = importlib.import_module("modules.memory.daily_cycle")
    assert hasattr(m, "build_daily_narrative"), "helper build_daily_narrative otsutstvuet"
    # Synthetic summary of the day
    summary = {
        "text": "Give the results: 5 entries; emotional background + (0.50); main topics: deployment, tesc, blind.",
        "meta": {
            "emo": 0.5,
            "terms": ["deploy", "tests", "sleep"],
            "types": {"event": 4, "fact": 1},
        },
    }
    insights = [
        {"id":"1","title":"Glavnyy vyvod dnya"},
        {"id":"2","title":"Key topics of the day"},
        {"id":"3","title":"Emotional background of the day"},
    ]
    s = m.build_daily_narrative(summary, insights)
    assert isinstance(s, str) and len(s) > 10
    assert "Glavnye temy" in s or "Vyvody dnya" in s