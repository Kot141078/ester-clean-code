# -*- coding: utf-8 -*-
"""
tests/smoke/test_thinking_experience_context_adapter.py
"""
from __future__ import annotations

import os
import sys
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_experience_context_adapter_import_and_call():
    m = importlib.import_module("modules.thinking.experience_context_adapter")
    assert hasattr(m, "get_experience_context")
    s = m.get_experience_context()
    assert isinstance(s, str)