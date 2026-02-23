#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Periodicheskiy restore-drill.
ENV:
  RESTORE_DRILL_INTERVAL_HOURS=24
"""
import os
import sys
import time

from scripts.restore_drill import main as drill_main  # reuse if we expose main

# Backward compatibility: if restore_drill.py has no main(), we import and call as script via exec.
try:
    import types
    from importlib import import_module

    mod = import_module("scripts.restore_drill")
    if hasattr(mod, "main"):

        def run():
            return mod.main()

    else:

        def run():
            import subprocess

            return subprocess.call([sys.executable, "-m", "scripts.restore_drill"])

except Exception:

    def run():
        import subprocess

        return subprocess.call([sys.executable, "-m", "scripts.restore_drill"])


interval_h = float(os.getenv("RESTORE_DRILL_INTERVAL_HOURS", "24"))
interval = max(60.0, interval_h * 3600.0)

print(f"[restore-cron] interval={interval_h}h")
while True:
    rc = run()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[restore-cron] {ts} run rc={rc}")
    time.sleep(interval)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Periodicheskiy restore-drill.
ENV:
  RESTORE_DRILL_INTERVAL_HOURS=24
"""
import os
import sys
import time

from scripts.restore_drill import main as drill_main  # reuse if we expose main
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Backward compatibility: if restore_drill.py has no main(), we import and call as script via exec.
try:
    import types
    from importlib import import_module

    mod = import_module("scripts.restore_drill")
    if hasattr(mod, "main"):

        def run():
            return mod.main()

    else:

        def run():
            import subprocess

            return subprocess.call([sys.executable, "-m", "scripts.restore_drill"])

except Exception:

    def run():
        import subprocess

        return subprocess.call([sys.executable, "-m", "scripts.restore_drill"])


interval_h = float(os.getenv("RESTORE_DRILL_INTERVAL_HOURS", "24"))
interval = max(60.0, interval_h * 3600.0)

print(f"[restore-cron] interval={interval_h}h")
while True:
    rc = run()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[restore-cron] {ts} run rc={rc}")
# time.sleep(interval)