# -*- coding: utf-8 -*-
"""Compatibility module for the memory daily-cycle API.

The clean-code skeleton keeps the implementation in the repository-level
``daily_cycle`` module. This wrapper restores the legacy
``modules.memory.daily_cycle`` import path without starting runtime services.
"""

from __future__ import annotations

from daily_cycle import build_daily_narrative, run_cycle, status

__all__ = ["build_daily_narrative", "run_cycle", "status"]
