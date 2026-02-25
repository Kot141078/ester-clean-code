# -*- coding: utf-8 -*-
"""Grid-test vybora initsiativ po emotsiyam.
Pechataet tablitsu 5x5 po anxiety i interest (0.0..1.0 step 0.25).
Zapusk:
    python tests/manual/test_initiatives_matrix.py"""
from __future__ import annotations

from initiatives import choose_by_emotions
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def fmt(picks):
    return " | ".join(f"{p['tag']}:{p['title']}" for p in picks)


def main():
    steps = [0.00, 0.25, 0.50, 0.75, 1.00]
    print("=== Initiatives grid ===")
    for a in steps:
        for i in steps:
            emo = {"anxiety": a, "interest": i}
            picks = choose_by_emotions(emo)
            print(f"anx={a:.2f} int={i:.2f} -> {fmt(picks)}")
        print("-" * 80)


if __name__ == "__main__":
    main()
