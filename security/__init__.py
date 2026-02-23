# -*- coding: utf-8 -*-
"""Top-level security package shim (legacy compatibility).
MOSTY: (yavnyy) `from security import e2ee` — otdaem modul .e2ee.
ZEMNOY ABZATs: starye importy ne padayut, a poluchayut rabochuyu realizatsiyu.
c=a+b
"""
from __future__ import annotations
from . import e2ee as e2ee  # re-export
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
__all__ = ["e2ee"]