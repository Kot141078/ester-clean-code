# -*- coding: utf-8 -*-
"""
modules/ops/app_capabilities.py — proverka nalichiya prilozheniy i plan ustanovki.

Podderzhka:
- Windows: ischem ispolnyaemye cherez standartnye puti (Chrome, Notepad, PowerShell i t.p.)
- Linux: proveryaem cherez which

Installyatsiya:
- Plany tolko kak opisanie (oflayn). Ispolnenie — cherez otdelnyy shag: polzovatel ukazyvaet istochnik (put k .exe/.msi/.deb/.rpm),
  my delaem sistemnyy Start-Process/apt/dpkg/rpm — po zaprosu.

MOSTY:
- Yavnyy: (Kontekst ↔ Deystvie) esli «pokazhi X», a X net — formiruem volevoy zapros: «ukazhi istochnik, ustanovit?».
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) yavnyy plan snizhaet neozhidannosti pri ustanovke.
- Skrytyy #2: (Arkhitektura ↔ Bezopasnost) deystvie ustanovki gated cherez soglasie "install.*".

ZEMNOY ABZATs:
Rabotaet tselikom lokalno; ustanovka — tolko s podtverzhdennym putem fayla na diske/lokalnoy seti.

# c=a+b
"""
from __future__ import annotations
import os, platform, shutil
from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _is_windows() -> bool:
    return platform.system().lower().startswith("win")

def is_installed(app: str) -> bool:
    app = app.lower()
    if _is_windows():
        paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "notepad": r"C:\Windows\System32\notepad.exe",
            "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "cmd": r"C:\Windows\System32\cmd.exe",
        }
        if app in paths:
            return os.path.exists(paths[app])
        # generic search in PATH
        return shutil.which(app) is not None
    else:
        # Linux
        candidates = {
            "xterm": "/usr/bin/xterm",
            "thunar": "/usr/bin/thunar",
            "chrome": "/usr/bin/google-chrome",
            "chromium": "/usr/bin/chromium",
        }
        if app in candidates:
            return os.path.exists(candidates[app])
        return shutil.which(app) is not None

def install_plan(app: str) -> Dict[str, str]:
    app = app.lower()
    if _is_windows():
        return {
            "app": app,
            "strategy": "local_installer",
            "ask": "Ukazhi put k ustanovschiku (EXE/MSI) na diske/lokalke",
            "hint": "<PROJECT_ROOT>/Installers/ChromeSetup.exe"
        }
    else:
        return {
            "app": app,
            "strategy": "package_or_local",
            "ask": "Predpochtenie: paketnyy menedzher (apt/rpm) ili lokalnyy fayl? Ukazhi put/komandu.",
            "hint": "apt install ./chrome.deb  (ili) dpkg -i ./chrome.deb"
        }
