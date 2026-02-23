
"""Smoke-test: profilirovanie opyta s narrative summary_text."""
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_experience_profile_accepts_summary_text():
    exp = importlib.import_module("modules.memory.experience")
    info = {
        "insights": [
            {"title":"Glavnyy vyvod dnya", "text": "Glavnyy vyvod dnya"},
            {"title":"Klyuchevye temy dnya", "text": "Klyuchevye temy dnya"},
            {"title":"Emotsionalnyy fon dnya", "text": "Emotsionalnyy fon dnya"},
        ],
        "summary_text": "Segodnya bylo zapisey: 5; nastroenie v tselom polozhitelnoe. Glavnye temy: deploy, tests, sleep.",
    }
    profile = exp.make_profile_from_insights(info)
    assert profile["ok"] is True
    assert profile["total_insights"] >= 3
    assert any(isinstance(t,str) and t for t in profile["top_terms"])