#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sinkhronizatsiya lokalnykh bekapov v oblako (S3 ili GDrive).
Skript ischet *.enc i sootvetstvuyuschie .sig v BACKUPS_DIR (po umolchaniyu ./backups)
i zagruzhaet, esli ikh esche net na tselevom provaydere.
ENV:
  BACKUPS_DIR=./backups
  BACKUP_PROVIDER=S3|GDRIVE
  # S3 nastroyki sm. cloud/s3_adapter.py
  # GDrive: GDRIVE_SERVICE_ACCOUNT_FILE, GDRIVE_BACKUP_FOLDER_ID
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROVIDER = os.getenv("BACKUP_PROVIDER", "S3").upper()
BACKUPS_DIR = os.getenv("BACKUPS_DIR", "./backups")
STATE_FILE = os.path.join(BACKUPS_DIR, ".sync_state.json")


def _load_state():
    try:
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        return {"uploaded": {}}


def _save_state(st):
    Path(BACKUPS_DIR).mkdir(parents=True, exist_ok=True)
    json.dump(st, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def _s3_list():
    from cloud.s3_adapter import list_keys

    return set(list_keys(prefix=""))


def _gdrive_list():
    from cloud.gdrive_adapter import list_files

    return {name: fid for fid, name in list_files(prefix="")}


def main():
    st = _load_state()
    encs = sorted(glob.glob(os.path.join(BACKUPS_DIR, "*.enc")))
    if PROVIDER == "S3":
        remote = _s3_list()
    else:
        remote_map = _gdrive_list()  # name -> id
        remote = set(remote_map.keys())

    uploaded = 0
    for enc in encs:
        sig = enc + ".sig"
        if not os.path.exists(sig):
            print(f"Skip (no sig): {enc}")
            continue
        base_name = os.path.basename(enc)
        if base_name in remote or st["uploaded"].get(base_name):
            print(f"Already uploaded: {base_name}")
            continue

        if PROVIDER == "S3":
            from cloud.s3_adapter import upload_file as s3_up

            s3_up(enc, base_name)
            s3_up(sig, base_name + ".sig")
            st["uploaded"][base_name] = True
            _save_state(st)
            uploaded += 1
            print(f"[S3] Uploaded {base_name} (+ .sig)")
        else:
            from cloud.gdrive_adapter import upload_file as gd_up

            fid1 = gd_up(enc, file_name=base_name)
            fid2 = gd_up(sig, file_name=base_name + ".sig")
            st["uploaded"][base_name] = True
            _save_state(st)
            uploaded += 1
            print(f"[GDRIVE] Uploaded {base_name} (+ .sig) -> {fid1}, {fid2}")

    print(f"Done. uploaded={uploaded} provider={PROVIDER}")


if __name__ == "__main__":
    main()