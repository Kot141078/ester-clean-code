# -*- coding: utf-8 -*-
"""windows/usb_agent_service.py - Windows Service dlya agenta "odin vopros".
Trebuet pywin32 (ustanavlivaetsya ustanovschikom; optsionalno).

Use (from administrator):
  python windows\\usb_agent_service.py install
  python windows\\usb_agent_service.py start
  python windows\\usb_agent_service.py stop
  python windows\\usb_agent_service.py remove

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Arkhitektura): sistemnyy servis daet avtozapusk i perezapusk.
- Skrytyy 1 (Nadezhnost ↔ Diagnostika): servisnyy log v Event Log Windows.
- Skrytyy 2 (Praktika ↔ Bezopasnost): net pravki myshleniya; only obolochka zapuska.

Zemnoy abzats:
Esli nuzhen imenno Service (a ne Planirovschik): etot modul krutit tsikl agenta v otdelnom potoke
i korrektno obrabatyvaet signaly Start/Stop ot Service Control Manager.

# c=a+b"""
from __future__ import annotations

import sys
import time
import threading
import json
import os

try:
    import win32serviceutil  # type: ignore
    import win32service  # type: ignore
    import win32event  # type: ignore
except Exception as e:  # noqa: BLE001
    print("pywin32 is required for Windows Service. Install via 'pip install pywin32'.", file=sys.stderr)
    raise

# We import our agent
from listeners.usb_one_question_agent import run_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class EsterUsbAgentService(win32serviceutil.ServiceFramework):  # type: ignore
    _svc_name_ = "EsterUsbAgent"
    _svc_display_name_ = "Ester USB One-Question Agent"
    _svc_description_ = "Zero-Touch USB agent for Ester. Prepares /ESTER and optionally deploys release."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)  # type: ignore
        self.running = False
        self.thread: threading.Thread | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)  # type: ignore
        self.running = False
        win32event.SetEvent(self.stop_event)  # type: ignore

    def SvcDoRun(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="EsterUsbAgentLoop", daemon=True)
        self.thread.start()
        # Zhdem ostanovku
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)  # type: ignore

    def _loop(self):
        interval = int(os.getenv("ESTER_ZT_POLL_INTERVAL", "5") or 5)
        archive = os.getenv("ESTER_USB_DEPLOY_ARCHIVE", "").strip() or None
        dump = os.getenv("ESTER_USB_DEPLOY_DUMP", "").strip() or None
        ab_mode = (os.getenv("AB_MODE") or "A").strip().lower()
        while self.running:
            try:
                rep = run_once(archive=archive, dump=dump, ab_mode=ab_mode)
                # You can write JSION to a file/log - as needed
                _ = json.dumps(rep)  # serialization check
            except Exception:
                pass
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(EsterUsbAgentService)  # type: ignore
# c=a+b
