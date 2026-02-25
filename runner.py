# -*- coding: utf-8 -*-
"""Kornevoy runner - proksi k modules.act.runner.

MOSTY:
- Yavnyy: (routes.* ↔ modules.act.runner) re-export start/stop/status.
- Skrytyy #1: vychischeny future-importy, chtoby import byl “sterilnym”.
- Skrytyy #2: nulevoy kod na import - menshe shansov na rannie pobochki.

ZEMNOY ABZATs:
Eto "udlinitel": pust routy berut runner zdes, a logika - there, where ey place.

# c=a+b"""
from modules.act.runner import start, stop, status  # re-export
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["start", "stop", "status"]
# c=a+b