
"""Smoke-test narrativnoy svodki dnya."""
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_daily_narrative_helper_exists_and_works():
    m = importlib.import_module("modules.memory.daily_cycle")
    assert hasattr(m, "build_daily_narrative"), "helper build_daily_narrative otsutstvuet"
    # Sinteticheskaya svodka dnya
    summary = {
        "text": "Itogi day: zapisey 5; emotsionalnyy fon + (0.50); osnovnye temy: deploy, tests, sleep.",
        "meta": {
            "emo": 0.5,
            "terms": ["deploy", "tests", "sleep"],
            "types": {"event": 4, "fact": 1},
        },
    }
    insights = [
        {"id":"1","title":"Glavnyy vyvod dnya"},
        {"id":"2","title":"Klyuchevye temy dnya"},
        {"id":"3","title":"Emotsionalnyy fon dnya"},
    ]
    s = m.build_daily_narrative(summary, insights)
    assert isinstance(s, str) and len(s) > 10
    assert "Glavnye temy" in s or "Vyvody dnya" in s