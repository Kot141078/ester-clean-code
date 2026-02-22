# -*- coding: utf-8 -*-
"""Compatibility bridge so `from modules.mm_compat import ...` loads real helpers."""
from __future__ import annotations

from mm_compat import patch as patch  # noqa: F401
from mm_compat import patch_memory_manager as patch_memory_manager  # noqa: F401

__all__ = ["patch", "patch_memory_manager"]
