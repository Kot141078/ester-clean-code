# -*- coding: utf-8 -*-
"""observability/messaging_stats.py - metriki po kanalam i ocheredyam.

MOSTY:
- (Yavnyy) collect_messaging_stats(now_ts=None) → slovar dlya bordy/alertov (1ch/24ch, kody oshibok, ocheredi).
- (Skrytyy #1) Istochniki: outbox, nudges_pending, nudges_log — bez izmeneniy skhem ranee addavlennykh moduley.
- (Skrytyy #2) Safe defolty: esli tablits net, vozvraschaem nuli (borda ne padaet).

ZEMNOY ABZATs:
Odin vyzov - i u vas kartina: skolko ushlo/ne ushlo, chto v ocheredi, chto “gorit” i kakie kody byut chasche vsego.

# c=a+b"""
from __future__ import annotations

import os, time, sqlite3
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB_PATH = os.getenv("MESSAGING_DB_PATH", "data/messaging.db")

def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def _exists(c: sqlite3.Connection, table: str) -> bool:
    r = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(r)

def collect_messaging_stats(now_ts: float | None = None) -> Dict[str, Any]:
    now = float(now_ts or time.time())
    hour_ago = now - 3600
    day_ago  = now - 86400

    out: Dict[str, Any] = {
        "ts": int(now),
        "channels": {
            "telegram": {"sent_1h":0,"fail_1h":0,"sent_24h":0,"fail_24h":0,"top_errors":[]},
            "whatsapp":{"sent_1h":0,"fail_1h":0,"sent_24h":0,"fail_24h":0,"top_errors":[]},
        },
        "queue": {"pending_total":0,"pending_due":0,"overdue_due":0},
        "log": {"sent_24h":0,"fail_24h":0}
    }

    with _conn() as c:
        # otbox - successes/errors by channel
        if _exists(c, "outbox"):
            for ch in ("telegram","whatsapp"):
                s1 = c.execute("SELECT COUNT(*) FROM outbox WHERE ts>=? AND channel=? AND status LIKE 'ok%'", (hour_ago,ch)).fetchone()[0]
                f1 = c.execute("SELECT COUNT(*) FROM outbox WHERE ts>=? AND channel=? AND status NOT LIKE 'ok%'", (hour_ago,ch)).fetchone()[0]
                s24 = c.execute("SELECT COUNT(*) FROM outbox WHERE ts>=? AND channel=? AND status LIKE 'ok%'", (day_ago,ch)).fetchone()[0]
                f24 = c.execute("SELECT COUNT(*) FROM outbox WHERE ts>=? AND channel=? AND status NOT LIKE 'ok%'", (day_ago,ch)).fetchone()[0]
                out["channels"][ch]["sent_1h"]  = int(s1);  out["channels"][ch]["fail_1h"]  = int(f1)
                out["channels"][ch]["sent_24h"] = int(s24); out["channels"][ch]["fail_24h"] = int(f24)
                # top kodov
                rows = c.execute("""
                    SELECT COALESCE(http_status,0) AS code, COUNT(*) AS cnt
                      FROM outbox
                     WHERE ts>=? AND channel=? AND status NOT LIKE 'ok%'
                  GROUP BY code ORDER BY cnt DESC LIMIT 5
                """, (day_ago,ch)).fetchall()
                out["channels"][ch]["top_errors"] = [{"code": int(r[0] or 0), "count": int(r[1] or 0)} for r in rows]

        # newges_pending/log - queue status
        if _exists(c, "nudges_pending"):
            total = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new'").fetchone()[0]
            due   = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new' AND due_ts<=?", (now,)).fetchone()[0]
            over  = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new' AND due_ts<?", (now,)).fetchone()[0]
            out["queue"] = {"pending_total": int(total or 0), "pending_due": int(due or 0), "overdue_due": int(over or 0)}

        if _exists(c, "nudges_log"):
            s24 = c.execute("SELECT COUNT(*) FROM nudges_log WHERE ts>=? AND status LIKE 'ok%'", (day_ago,)).fetchone()[0]
            f24 = c.execute("SELECT COUNT(*) FROM nudges_log WHERE ts>=? AND status NOT LIKE 'ok%'", (day_ago,)).fetchone()[0]
            out["log"] = {"sent_24h": int(s24 or 0), "fail_24h": int(f24 or 0)}

    return out