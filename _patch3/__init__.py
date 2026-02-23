"""Legacy patch namespace guard for _patch3.

This directory is not canonical runtime code.
Set ESTER_LAB_MODE=1 only for lab experiments.
"""

from __future__ import annotations

import os
import warnings


_MSG = (
    "LEGACY PATCH DIR imported; this is not canonical. "
    "Use modules/, routes/, and services/ instead."
)

warnings.warn(_MSG, RuntimeWarning, stacklevel=2)

if os.getenv("ESTER_LAB_MODE", "0").strip() != "1":
    raise ImportError(
        _MSG + " Import is blocked unless ESTER_LAB_MODE=1 (lab mode)."
    )

