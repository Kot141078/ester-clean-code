# -*- coding: utf-8 -*-
"""
modules/agents/game_mate_agent.py — «Igrovoy naparnik» (lokalnaya model vzaimodeystviya).

Podderzhka:
  - prostye poshagovye igry (tic-tac-toe, 2048-like) — raschet khoda, zapis v pamyat.
  - rezhim «sovetchika»: vydaet plan i khod, vvod ostaetsya u polzovatelya/inogo protsessa.

Operatsii (kind):
  - ttt_suggest  meta: {"board":[...], "me":"X|O"}   # krestiki-noliki
  - move_note    meta: {"game":"name","move":"..."}

MOSTY:
- Yavnyy: (Mysl ↔ Deystvie) — khod = deystvie, prokhodit cherez safety (nizkiy risk).
- Skrytyy #1: (Memory ↔ Obuchenie) — khranit khody kak opyt.
- Skrytyy #2: (Kibernetika ↔ Strategiya) — petlya: predlozhenie → otklik → retro.

ZEMNOY ABZATs:
Inzhenerno — malenkiy mozg dlya igr, bez privyazki k konkretnym klientam.
Prakticheski — Ester «podskazyvaet i igraet ryadom» bezopasnym sposobom.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from modules.agents.base_agent import AgentBase, Action
from modules.memory import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class GameMateAgent(AgentBase):
    def __init__(self):
        super().__init__("game_mate")

    def plan(self, a:Action):
        k=a.kind; m=a.meta or {}
        if k=="ttt_suggest":
            board=m.get("board") or [" "]*9
            me=(m.get("me") or "X").upper()
            move=self._ttt_best_move(board, me)
            plan=[{"do":"game_suggest","game":"tic-tac-toe","move":move}]
            return plan, {"move":move}
        elif k=="move_note":
            plan=[{"do":"log_move","game":m.get("game",""),"move":m.get("move","")}]
            return plan, {}
        else:
            return [{"do":"noop"}], {}

    def _ttt_best_move(self, b, me)->int:
        # prostaya evristika: vyigrat → tsentr → ugol → rendom
        wins=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        # 1) pobednyy khod
        for i in range(9):
            if b[i]==" ":
                bb=b[:]; bb[i]=me
                if any(bb[x]==bb[y]==bb[z]==me for x,y,z in wins): return i
        # 2) tsentr
        if b[4]==" ": return 4
        # 3) ugol
        for i in [0,2,6,8]:
            if b[i]==" ": return i
        # 4) pervoe pustoe
        for i in range(9):
            if b[i]==" ": return i
        return 0