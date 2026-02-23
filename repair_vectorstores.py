# repair_vectorstores.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import glob
import json
import os
import shutil
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def is_valid_json(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception:
        return False


def latest_backup_for(store_path: str):
    patt = store_path + ".bak.*"
    files = sorted(glob.glob(patt), reverse=True)
    return files[0] if files else None


def main():
    root = os.getcwd()
    checked = 0
    repaired = 0
    print(f"[i] Scan under: {root}")
    for dirpath, _, filenames in os.walk(root):
        if "store.json" in filenames:
            store = os.path.join(dirpath, "store.json")
            checked += 1
            if is_valid_json(store):
                print(f"[OK] {store}")
                continue
            bak = latest_backup_for(store)
            if not bak:
                print(f"[!!] Broken, no backup: {store}")
                continue
            print(f"[fix] {store}  <=  {os.path.basename(bak)}")
            shutil.copy2(bak, store)
            repaired += 1
    print(f"\nChecked: {checked}, repaired: {repaired}")


if __name__ == "__main__":
    main()