# -*- coding: utf-8 -*-
"""
modules.safety — gruppa utilit dlya odobreniy i kvoruma.
"""
from __future__ import annotations

from .guardian import create_approval, validate_approval
from .quorum import require_quorum

__all__ = ["create_approval", "validate_approval", "require_quorum"]
