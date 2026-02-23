# -*- coding: utf-8 -*-
"""Optional hub stub.

Some deployments reference `from hub import create_hub`. If you do not use a hub,
this stub prevents ImportError and provides a predictable, auditable no-op.
"""

from __future__ import annotations

from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def create_hub(app: Any = None) -> Dict[str, Any]:
    # Keep it minimal. You can later extend with real registries.
    return {
        "enabled": False,
        "reason": "stub",
        "app": app,
    }