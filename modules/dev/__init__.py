# -*- coding: utf-8 -*-
"""
Dev utilities package.
Exports diagnostics blueprint as 'diagnostics_bp' for easy import in app.py
"""
from .diagnostics import bp as diagnostics_bp  # noqa: F401
from modules.memory.facade import memory_add, ESTER_MEM_FACADE