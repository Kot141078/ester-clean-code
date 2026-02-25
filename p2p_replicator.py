# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class PeerReplicator:
    """Lightweight Replicator:
      - takes a list of peers from REPLICATION_PERS (separated by commas) or from self.peers
      - has methods status() and pull_end()"""

    def __init__(
        self,
        peers: Optional[List[str]] = None,
        token: Optional[str] = None,
        interval_sec: int = 30,
        **_kwargs: Any,
    ):
        env_peers = [
            p.strip() for p in (os.getenv("REPLICATION_PEERS", "")).split(",") if p.strip()
        ]
        self.peers: List[str] = peers or env_peers
        self.token: str = str(token or os.getenv("REPLICATION_TOKEN", "")).strip()
        self.interval_sec: int = max(1, int(interval_sec or 30))
        self.running: bool = False
        self.last_pull: Optional[float] = None
        self.last_report: Dict[str, Any] = {}

    def status(self) -> Dict[str, Any]:
        return {
            "peers": self.peers,
            "running": bool(self.running),
            "interval_sec": int(self.interval_sec),
            "last_pull": self.last_pull,
            "last_report": self.last_report,
        }

    def pull_once(self) -> Dict[str, Any]:
        token = self.token or os.getenv("REPLICATION_TOKEN", "")
        reports = {}
        for peer in self.peers:
            try:
                url = peer.rstrip("/") + "/replication/snapshot"
                headers = {"X-REPL-TOKEN": token} if token else {}
                r = requests.get(url, headers=headers, timeout=15)
                # apply locally via /replication/appli
                sig = r.headers.get("X-Signature", "")
                if not sig or not r.content:
                    reports[peer] = {"ok": False, "error": "no snapshot or signature"}
                    continue
                # lokalnoe primenenie (cherez localhost)
                local = "http://127.0.0.1:" + os.getenv("PORT", "8000") + "/replication/apply"
                r2 = requests.post(
                    local,
                    headers={"X-REPL-TOKEN": token, "X-Signature": sig},
                    data=r.content,
                    timeout=15,
                )
                reports[peer] = {"ok": r2.status_code == 200}
            except Exception as e:
                reports[peer] = {"ok": False, "error": str(e)}
        self.last_pull = time.time()
        pulled = sum(1 for rep in reports.values() if isinstance(rep, dict) and rep.get("ok"))
        self.last_report = {"pulled": pulled, "reports": reports}
        return {"ok": True, "pulled": pulled, "reports": reports}
