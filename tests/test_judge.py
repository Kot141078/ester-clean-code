# -*- coding: utf-8 -*-
from judge_combiner import combine_answers, pick_best_local
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_pick_best_and_combine_local():
    answers = [
        "Korotkiy otvet.",
        "Razvernutyy otvet:\n- punkt 1\n- punkt 2\nVyvod: vse yasno.",
        "Sredniy po dline otvet s paroy predlozheniy. On strukturirovan.",
    ]
    best, meta = pick_best_local(answers)
    assert best in answers
    assert meta["strategy"] == "heuristic_local"
    out = combine_answers(
        prompt="Testovyy zapros", local_answers=answers, mode="local"
    )
    assert out["mode"] == "local"
    assert out["final"] in answers
# assert out["used_candidates"] == len(answers)