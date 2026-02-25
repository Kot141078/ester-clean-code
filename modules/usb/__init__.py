
# -*- coding: utf-8 -*-
"""modules.usb - dinamicheskiy most k USB slushatelyam/drayveram.
Mosty:
- Yavnyy: (modules.usb.X ↔ listeners.usb_X) - __getattr__ podbiraet realizatsiyu.
- Skrytyy #1: (Setevoe telo ↔ I/O) - edinoobraznyy vkhod dlya USB-potokov.
- Skrytyy #2: (DX ↔ Nadezhnost) — A/B-slot s myagkim otkatom.

Zemnoy abzats:
Kogda kod zhdet `modules.usb.scanner`, a est `listeners/usb_scanner.py`, etot paket pomogaet “skhlopnut” importy bez pravok.
# c=a+b"""
from __future__ import annotations
import importlib, os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_COMPAT_AB","A").upper()

def __getattr__(name: str):
    candidates = [f"listeners.usb_{name}", f"usb.{name}"]
    last_err = None
    for target in candidates:
        try:
            return importlib.import_module(target)
        except Exception as e:
            last_err = e
            continue
    raise AttributeError(f"modules.usb: cannot resolve '{name}': {last_err}")