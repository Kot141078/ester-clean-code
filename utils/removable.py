# -*- coding: utf-8 -*-
"""
utils/removable.py — opredelenie podklyuchennykh semnykh tomov (Windows/Linux/macOS) bez vneshnikh zavisimostey.

API:
  list_removable() -> List[dict]  # [{'mount':'X:\\','device':'...','fs':'...','label':'...','size':int,'free':int,'platform':'win'|'linux'|'darwin'}]

Mosty:
- Yavnyy (Inzheneriya ↔ UX): daem operatoru bezopasnyy spisok tochek zapisi.
- Skrytyy 1 (Infoteoriya ↔ Minimalizm): tolko stdlib, minimum dopuscheniy.
- Skrytyy 2 (Praktika ↔ Bezopasnost): nikakogo formatirovaniya; tolko chtenie metadannykh.

Zemnoy abzats:
Eto «sensor osyazaniya»: gde smontirovany semnye nositeli i skolko na nikh mesta — chtoby korrektno razlozhit /ESTER.

# c=a+b
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _win_list() -> List[Dict]:
    import ctypes
    from ctypes import wintypes

    DRIVE_REMOVABLE = 2
    GetLogicalDrives = ctypes.windll.kernel32.GetLogicalDrives
    GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
    GetDiskFreeSpaceExW = ctypes.windll.kernel32.GetDiskFreeSpaceExW
    GetVolumeInformationW = ctypes.windll.kernel32.GetVolumeInformationW

    res: List[Dict] = []
    mask = GetLogicalDrives()
    for i in range(26):
        if mask & (1 << i):
            letter = f"{chr(65+i)}:\\"
            dtype = GetDriveTypeW(wintypes.LPCWSTR(letter))
            if dtype != DRIVE_REMOVABLE:
                continue
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            GetDiskFreeSpaceExW(wintypes.LPCWSTR(letter), None, ctypes.byref(total_bytes), ctypes.byref(free_bytes))
            label_buf = ctypes.create_unicode_buffer(260)
            fs_buf = ctypes.create_unicode_buffer(260)
            sn = ctypes.c_uint(0)
            max_comp = ctypes.c_uint(0)
            flags = ctypes.c_uint(0)
            try:
                ok = GetVolumeInformationW(
                    wintypes.LPCWSTR(letter),
                    label_buf, 260,
                    ctypes.byref(sn),
                    ctypes.byref(max_comp),
                    ctypes.byref(flags),
                    fs_buf, 260
                )
            except Exception:
                ok = 0
            label = label_buf.value if ok else ""
            fs = fs_buf.value if ok else ""
            res.append({
                "mount": letter,
                "device": letter,
                "fs": fs,
                "label": label,
                "size": int(total_bytes.value or 0),
                "free": int(free_bytes.value or 0),
                "platform": "win",
            })
    return res

def _linux_list() -> List[Dict]:
    res: List[Dict] = []
    try:
        mounts = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
    except Exception:
        mounts = []
    for line in mounts:
        parts = line.split()
        if len(parts) < 3:
            continue
        dev, mnt, fs = parts[0], parts[1], parts[2]
        # grubaya evristika «semnosti»
        if not dev.startswith("/dev/"):
            continue
        base = Path(dev).name  # sdb1 -> sdb1
        root = "".join([c for c in base if not c.isdigit()]).rstrip("0123456789")  # sdb1 -> sdb
        rem_flag = Path(f"/sys/block/{root}/removable")
        is_rem = False
        try:
            is_rem = rem_flag.exists() and rem_flag.read_text().strip() == "1"
        except Exception:
            pass
        if not is_rem:
            continue
        try:
            st = os.statvfs(mnt)
            size = int(st.f_frsize * st.f_blocks)
            free = int(st.f_frsize * st.f_bavail)
        except Exception:
            size = 0
            free = 0
        res.append({"mount": mnt, "device": dev, "fs": fs, "label": "", "size": size, "free": free, "platform": "linux"})
    return res

def _darwin_list() -> List[Dict]:
    res: List[Dict] = []
    # Prostaya evristika: vse iz /Volumes schitaem vneshnim.
    vols = Path("/Volumes")
    if vols.exists():
        for p in vols.iterdir():
            if not p.is_dir():
                continue
            mnt = str(p)
            try:
                st = os.statvfs(mnt)
                size = int(st.f_frsize * st.f_blocks)
                free = int(st.f_frsize * st.f_bavail)
            except Exception:
                size = 0
                free = 0
            res.append({"mount": mnt, "device": mnt, "fs": "", "label": p.name, "size": size, "free": free, "platform": "darwin"})
    return res

def list_removable() -> List[Dict]:
    if sys.platform.startswith("win"):
        return _win_list()
    if sys.platform.startswith("linux"):
        return _linux_list()
    if sys.platform.startswith("darwin"):
        return _darwin_list()
    return []

if __name__ == "__main__":
    print(json.dumps(list_removable(), ensure_ascii=False, indent=2))
# c=a+b