# -*- coding: utf-8 -*-
"""Alias ​​for connecting Esther selfmod-ville bridge without editing the core app.po."""

from modules.ester.selfmod_will_bridge import bp_ester_selfmod_will  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["bp_ester_selfmod_will"]