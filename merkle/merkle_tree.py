# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Tuple

from .cas import _digest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class Merkle:
    @staticmethod
    def build(leaves: List[bytes]) -> Tuple[str, List[List[str]]]:
        # vozvraschaet (root, levels) — urovni ot listev k kornyu
        if not leaves:
            return _digest(b""), []
        level = [_digest(x) for x in leaves]
        levels = [level]
        while len(level) > 1:
            nxt = []
            it = iter(level)
            for a in it:
                b = next(
                    it, a
                )  # dubliruem posledniy pri nechetnom kolichestve
                nxt.append(_digest((a + b).encode("utf-8")))
            level = nxt
            levels.append(level)
        return level[0], levels
