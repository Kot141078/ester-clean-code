# -*- coding: utf-8 -*-
"""modules.safety - a group of utilities for fertilizers and quorum."""
from __future__ import annotations

from .guardian import create_approval, validate_approval
from .quorum import require_quorum

__all__ = ["create_approval", "validate_approval", "require_quorum"]
