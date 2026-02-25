
"""Smoke-test: profilirovanie opyta s narrative summary_text."""
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_experience_profile_accepts_summary_text():
    exp = importlib.import_module("modules.memory.experience")
    info = {
        "insights": [
            {"title":"Glavnyy vyvod dnya", "text": "Glavnyy vyvod dnya"},
            {"title":"Key topics of the day", "text": "Key topics of the day"},
            {"title":"Emotional background of the day", "text": "Emotional background of the day"},
        ],
        "summary_text": "There were 5 entries today; the mood is generally positive. Main topics: deployment, test, blind.",
    }
    profile = exp.make_profile_from_insights(info)
    assert profile["ok"] is True
    assert profile["total_insights"] >= 3
    assert any(isinstance(t,str) and t for t in profile["top_terms"])