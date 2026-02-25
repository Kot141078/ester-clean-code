# -*- coding: utf-8 -*-
"""Legacy forwarder to modules.thinking.think_core.THINKER/etc.
MOSTY: (yavnyy) legacy import path; (skrytye) kaskad↔agenty, konfig↔sostoyanie.
ZEMNOY ABZATs: starye plaginy mogut importirovat THINKER po staromu puti - vse vzletit.
# c=a+b"""
from __future__ import annotations
from modules.thinking.think_core import *  # type: ignore  # noqa: F401,F403
from modules.memory.facade import memory_add, ESTER_MEM_FACADE