# -*- coding: utf-8 -*-
from judge_combiner import combine_answers, pick_best_local
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_pick_best_and_combine_local():
    answers = [
        "Short answer.",
        "Detailed answer:\n- point 1\n- point 2\nConclusion: everything is clear.",
        "Average length answer with a couple of sentences. It's structured.",
    ]
    best, meta = pick_best_local(answers)
    assert best in answers
    assert meta["strategy"] == "heuristic_local"
    out = combine_answers(
        prompt="Test request", local_answers=answers, mode="local"
    )
    assert out["mode"] == "local"
    assert out["final"] in answers
# assert out["used_candidates"] == len(answers)