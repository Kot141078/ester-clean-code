# -*- coding: utf-8 -*-
"""scripts/auto_backup.py - avtonomnyy sistemnyy bekap + mayak + sobytie.

Use (systemd timer vyzyvaet bez argumentov):
    python -m scripts.auto_backup

ENV (optional):
- PERSIST_DIR, BACKUP_DIR - kak v config_backup.py
- BACKUP_BEACON_KIND — vid sobytiya (po umolchaniyu "backup.run"/"backup.done"/"backup.fail")"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Any, Dict

# Kanonovye moduli
from config_backup import create_backup, verify_backup
from modules import events_bus
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _meta(kind: str, status: str, note: str = "") -> Dict[str, Any]:
    return {
        "trace_id": "",  # sgeneritsya v events_bus.append
        "correlation_id": "",
        "source": "auto_backup",
        "note": note or kind,
        "idempotency_key": f"auto_backup::{time.strftime('%Y%m%d%H%M')}",
    }


def main() -> int:
    kind_run = os.getenv("BACKUP_BEACON_KIND_RUN", "backup.run")
    kind_done = os.getenv("BACKUP_BEACON_KIND_DONE", "backup.done")
    kind_fail = os.getenv("BACKUP_BEACON_KIND_FAIL", "backup.fail")

    # Mayak: start
    events_bus.append(kind_run, {"pid": os.getpid()}, meta=_meta(kind_run, "run"))

    try:
        zip_path, sig_path = create_backup()
        ok = verify_backup(zip_path)
        payload: Dict[str, Any] = {
            "zip": zip_path,
            "sig": sig_path,
            "verified": bool(ok),
        }
        events_bus.append(kind_done, payload, meta=_meta(kind_done, "done"))
        return 0
    except Exception as e:
        err = {"error": str(e), "traceback": traceback.format_exc().splitlines()[-10:]}
        events_bus.append(kind_fail, err, meta=_meta(kind_fail, "fail"))
        try:
            # Log just in case in STUDER YSON
            sys.stderr.write(json.dumps({"ok": False, **err}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())