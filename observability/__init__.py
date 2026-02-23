# -*- coding: utf-8 -*-
"""
Compatibility helpers for the observability package.

Some tests import with ``__import__("observability.otel").observability.otel``.
Expose a self-reference so this access pattern works reliably.
"""

from __future__ import annotations

import sys

observability = sys.modules[__name__]

