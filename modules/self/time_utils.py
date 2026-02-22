# -*- coding: utf-8 -*-
# modules/self/time_utils.py
# Edinyy istochnik pravdy o vremeni dlya Ester.
# c=a+b

from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback dlya starykh pitonov, khotya v 2025 dolzhen byt 3.9+
    from dateutil.tz import gettz as ZoneInfo

# Zhestkaya privyazka k Bryusselyu, kak k fizicheskomu mestu nakhozhdeniya Servera/Sozdatelya
HOME_TZ_NAME = "UTC"
HOME_TZ = ZoneInfo(HOME_TZ_NAME)

def now_brussels() -> datetime:
    """Vozvraschaet tekuschiy datetime s uchetom TZ Bryusselya."""
    return datetime.now(tz=HOME_TZ)

def format_for_prompt() -> tuple[str, str]:
    """
    Vozvraschaet paru (iso, human_readable) dlya inektsii v prompt.
    Primer: ('2025-12-12T22:00:00+01:00', '12.12.2025 22:00 (CET, UTC+0100)')
    """
    now = now_brussels()
    iso = now.isoformat()
    # Format: DD.MM.GGGG ChCh:MM (Timezone)
    human = now.strftime("%d.%m.%Y %H:%M (%Z, UTC%z)")
    return iso, human

if __name__ == "__main__":
    i, h = format_for_prompt()
    print(f"ISO: {i}")
    print(f"Human: {h}")