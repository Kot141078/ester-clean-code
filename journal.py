# -*- coding: utf-8 -*-
"""journal.py (root wrapper)

Esli v proekte est DVA fayla:
  D:\ester-project\journal.py
  D:\ester-project\modules\memory\journal.py

to `import journal` pochti navernyaka podkhvatit VERKhNIY (root) i nachnetsya ad.
This fayl delaet root-journal bezopasnym: on prosto reeksportiruet kanonicheskiy modul.

Recommenduemoe: voobsche pereimenovat/udalit root journal.py.
Esli udalit nelzya - ostav etot wrapper."""

from __future__ import annotations

from modules.memory.journal import *  # noqa: F401,F403
from modules.memory.facade import memory_add, ESTER_MEM_FACADE