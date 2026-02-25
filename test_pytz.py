from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import (  # Added for full test (extension: simulates Evkueoe)
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
    # Extension: test scheduler init (as in Evkueoye)
    scheduler = AsyncIOScheduler(timezone=tz)
    print(f"AsinkIOScheduler init with c: ZZF0Z - ok, Esther is ready for the schedule!")
    print("Passed test - Esther can remember time without whims.")
except Exception as e:
    print(f"Test failed: {str(e)}")
    import traceback

    print(traceback.format_exc())  # Complete truck for diagnostics