# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.garage.templates.registry import (
    CAPABILITY_ACTIONS,
    STABLE_ACTION_ALIASES,
    capability_policy_filter,
    create_agent_from_template,
    get_template,
    list_templates,
    render_plan,
    render_spec,
    resolve_allowed_actions,
)

__all__ = [
    "CAPABILITY_ACTIONS",
    "STABLE_ACTION_ALIASES",
    "capability_policy_filter",
    "resolve_allowed_actions",
    "list_templates",
    "get_template",
    "render_spec",
    "render_plan",
    "create_agent_from_template",
]
