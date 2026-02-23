# -*- coding: utf-8 -*-
"""
Compatibility shim for legacy path:
bin/messaging/telegram_adapter.py1.py

Delegates to messaging/telegram_adapter.py1.py.
"""
from __future__ import annotations

import runpy
from pathlib import Path


TARGET = Path(__file__).resolve().parents[2] / "messaging" / "telegram_adapter.py1.py"


def main() -> int:
    runpy.run_path(str(TARGET), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

