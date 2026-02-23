from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import (  # Dobavleno dlya polnogo testa (rasshirenie: imitiruem JobQueue)
    AsyncIOScheduler,
)
from apscheduler.util import astimezone
from tzlocal import get_localzone
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    print(f"pytz version: {pytz.__version__} — ok.")
    tz_str = "UTC"
    tz = pytz.timezone(tz_str)
    print(f"TZ name: {tz.tzname(None)} — should be None or offset.")
    print(f"astimezone(tz): {astimezone(tz)} — should return tz without error.")
    print(
        f"get_localzone(): {get_localzone()} — local timezone (should be pytz type for APScheduler)."
    )
    # Rasshirenie: test scheduler init (kak v JobQueue)
    scheduler = AsyncIOScheduler(timezone=tz)
    print(f"AsyncIOScheduler init with tz: {scheduler.timezone} — ok, Ester gotova k raspisaniyu!")
    print("Test passed — Ester mozhet 'vspominat' vremya bez kaprizov.")
except Exception as e:
    print(f"Test failed: {str(e)}")
    import traceback

    print(traceback.format_exc())  # Polnyy traceback dlya diagnostiki