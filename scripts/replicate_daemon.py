# -*- coding: utf-8 -*-
"""scripts/replicate_daemon.py - periodicheskiy pull-demon P2P replikatsii.
Ne menyaet kanon: ispolzuet p2p_replicator.PeerReplicator().pull_once()
Intervaly upravlyayutsya cherez REPLICATION_PULL_INTERVAL_SECS (defolt 30)."""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from typing import Any, Dict

from p2p_replicator import PeerReplicator  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_run = True


def _handle_sig(signum, frame):
    global _run
    _run = False


signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)


def one_tick() -> Dict[str, Any]:
    rep = PeerReplicator()
    return rep.pull_once()


def main():
    interval = max(5, int(os.getenv("REPLICATION_PULL_INTERVAL_SECS", "30")))
    while _run:
        try:
            r = one_tick()
            print(json.dumps({"ts": int(time.time()), "report": r}, ensure_ascii=False))
        except Exception as e:
            print(
                json.dumps({"ts": int(time.time()), "error": str(e)}, ensure_ascii=False),
                file=sys.stderr,
            )
        # smooth sleep with flag check
        for _ in range(interval):
            if not _run:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()