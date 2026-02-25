# -*- coding: utf-8 -*-
# modules/self/time_utils.py
# Esther's single source of truth about time.
# c=a+b

from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Falbatsk for old pythons, although in 2025 there should be 3.ya+
    from dateutil.tz import gettz as ZoneInfo

# Strict binding to Brussels as the physical location of the Server/Creator
HOME_TZ_NAME = "UTC"
HOME_TZ = ZoneInfo(HOME_TZ_NAME)

def now_brussels() -> datetime:
    """Returns the current DateTime, taking into account the C Brussels."""
    return datetime.now(tz=HOME_TZ)

def format_for_prompt() -> tuple[str, str]:
    """Returns a pair (iso, human_readable) for injection into the prompt.
    Example: (b2025-12-12Ть22:00:00+01:00b, b12.12.2025 22:00 (NETWORK, UTS+0100)b)"""
    now = now_brussels()
    iso = now.isoformat()
    # Format: DD.MM.GGGG ChCh:MM (Timezone)
    human = now.strftime("%d.%m.%Y %H:%M (%Z, UTC%z)")
    return iso, human

if __name__ == "__main__":
    i, h = format_for_prompt()
    print(f"ISO: {i}")
    print(f"Human: {h}")