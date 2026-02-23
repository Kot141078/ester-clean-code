# -*- coding: utf-8 -*-
"""
scheduler.sync_job — minimalnyy sync_once
# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict

from modules.memory.facade import memory_add, ESTER_MEM_FACADE
from p2p_replicator import PeerReplicator


def _peers_from_env() -> list[str]:
    return [p.strip() for p in (os.getenv("REPLICATION_PEERS", "") or "").split(",") if p.strip()]


def sync_once() -> Dict[str, Any]:
    peers = _peers_from_env()
    if not peers:
        return {"ok": True, "visited": 0, "synced": 0, "failed": 0, "reports": {}}
    repl = PeerReplicator(peers=peers)
    try:
        res = repl.pull_once() or {}
        reports = res.get("reports") if isinstance(res, dict) else {}
        if not isinstance(reports, dict):
            reports = {}
        visited = len(peers)
        synced = sum(1 for _peer, rep in reports.items() if isinstance(rep, dict) and bool(rep.get("ok")))
        failed = max(0, visited - synced)
        return {
            "ok": bool(res.get("ok", True)),
            "visited": visited,
            "synced": synced,
            "failed": failed,
            "reports": reports,
        }
    except Exception as e:
        return {
            "ok": False,
            "visited": len(peers),
            "synced": 0,
            "failed": len(peers),
            "error": str(e),
            "reports": {},
        }
