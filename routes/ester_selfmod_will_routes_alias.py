# -*- coding: utf-8 -*-
"""
Alias dlya podklyucheniya Ester selfmod-will bridge bez pravki core app.py.
"""

from modules.ester.selfmod_will_bridge import bp_ester_selfmod_will  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["bp_ester_selfmod_will"]