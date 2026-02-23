# -*- coding: utf-8 -*-
from __future__ import annotations

# Backward-compatible alias for naming consistency in Iter19 contract.
from routes.initiative_routes import bp_initiatives as bp_initiatives  # noqa: F401
from routes.initiative_routes import register as register  # noqa: F401

__all__ = ["register", "bp_initiatives"]
