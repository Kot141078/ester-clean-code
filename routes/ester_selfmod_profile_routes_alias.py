# -*- coding: utf-8 -*-
"""Alias ​​for connecting Esther selfmod profile without editing the core app.po."""

from modules.ester.selfmod_profile import bp_ester_selfmod_profile  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["bp_ester_selfmod_profile"]