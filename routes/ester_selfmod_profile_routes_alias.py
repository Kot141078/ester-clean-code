# -*- coding: utf-8 -*-
"""
Alias dlya podklyucheniya Ester selfmod-profile bez pravki core app.py.
"""

from modules.ester.selfmod_profile import bp_ester_selfmod_profile  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["bp_ester_selfmod_profile"]