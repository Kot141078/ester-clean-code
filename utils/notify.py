# -*- coding: utf-8 -*-
"""utils/notify.py - legkie sistemnye uvedomleniya (best-effort, bez zavisimostey).

Poryadok popytok:
  • Linux: notify-send (if available).
  • macOS: osascript (display notification).
  • Windows: powershell (Write-Host + zvukovoy signal as minimum).
Never mind blokiruet vvod i ne trebuet GUI; pri otsutstvii instrumentov — tikhiy log.

Mosty:
- Yavnyy (Inzheneriya ↔ UX): odin best-effort vyzov - i dostatochno dlya refleksa.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): uvedomlenie — lish signal; reshenie ostaetsya za taymerom.
- Skrytyy 2 (Anatomiya ↔ Neyro): kak “kolokolchik” dlya refleksa — ne vmeshivaetsya v mozg, tolko ping.

Zemnoy abzats:
V prode uvedomleniya often ogranicheny politikami OS. Zdes strategiya “esli mozhno - podskazat operatoru”.

# c=a+b"""
from __future__ import annotations

import os
import platform
import subprocess
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _which(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None

def try_notify(title: str, message: str) -> None:
    try:
        sys = platform.system()
        if sys == "Linux" and _which("notify-send"):
            subprocess.Popen(["notify-send", title, message])
            return
        if sys == "Darwin" and _which("osascript"):
            safe_message = message.replace('"', "'")
            safe_title = title.replace('"', "'")
            script = f'display notification "{safe_message}" with title "{safe_title}"'
            subprocess.Popen(["osascript", "-e", script])
            return
        if sys == "Windows" and _which("powershell"):
            # Without BurntTuast: simple sound and recording - no blocking.
            safe_message_ps = message.replace("'", " ")
            safe_title_ps = title.replace("'", " ")
            code = f"[console]::beep(1000,200); Write-Host '{safe_title_ps}: {safe_message_ps}'"
            subprocess.Popen(["powershell", "-NoProfile", "-Command", code])
            return
    except Exception:
        pass
# c=a+b
