# -*- coding: utf-8 -*-
"""nudges/retry.py - analiz neuspeshnykh otpravok (outbox) i postanovka retraev v ochered.

MOSTY:
- (Yavnyy) analyze_and_requeue(flush_start_ts) scan outbox s momenta flush i sozdaet pending s due po raspisaniyu.
- (Skrytyy #1) Poisk sootvetstviya delaetsya cherez nudges_log (key+intent) → poluchaem event_id/kind bez izmeneniya send_broadcast().
- (Skrytyy #2) Dlya obkhoda UNIQUE(event_id,key,kind,intent) retrai ssylayutsya na newyy event 'NudgesRetry' (event_id otlichaetsya).

ZEMNOY ABZATs:
Esli soobschenie “ne ushlo” iz-za 503/429 i t.p., my ne zabyvaem - myagko poprobuem snova cherez 5 minut, potom cherez 30 minut, potom cherez 2 hours.

# c=a+b"""
from __future__ import annotations

import os, time, sqlite3
from typing import Any, Dict, List, Tuple

from nudges.store import _conn as _nudges_conn, read_event, add_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _codes() -> List[int]:
    raw = os.getenv("NUDGES_RETRY_CODES","429,500,502,503,504")
    out: List[int] = []
    for t in raw.split(","):
        t = t.strip()
        if not t: continue
        try: out.append(int(t))
        except: pass
    return out or [429,500,502,503,504]

def _schedule_minutes() -> List[int]:
    raw = os.getenv("NUDGES_RETRY_SCHEDULE","5m,30m,2h").lower().strip()
    if not raw: return [5,30,120]
    out: List[int] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.endswith("m"):
            n = int(tok[:-1] or "0"); out.append(n)
        elif tok.endswith("h"):
            n = int(tok[:-1] or "0"); out.append(n*60)
        else:
            try: out.append(int(tok))
            except: pass
    return out or [5,30,120]

def _has_pending_for(key: str, intent: str) -> bool:
    with _nudges_conn() as c:
        row = c.execute("SELECT 1 FROM nudges_pending WHERE status='new' AND key=? AND intent=? LIMIT 1",
                        (key, intent)).fetchone()
        return bool(row)

def _fails_count(key: str, intent: str) -> int:
    with _nudges_conn() as c:
        row = c.execute("SELECT COUNT(*) FROM nudges_log WHERE key=? AND intent=? AND status NOT LIKE 'ok%'", (key,intent)).fetchone()
        return int(row[0] or 0)

def analyze_and_requeue(flash_start_ts: float) -> int:
    """Returns the number of delivered retrays."""
    codes = set(_codes())
    sched = _schedule_minutes()
    now = time.time()
    requeued = 0

    with _nudges_conn() as c:
        # 1) we will take away unsuccessful outboxes from the moment of flush
        rows = c.execute("""
          SELECT ts, channel||':'||chat_id AS key, text, status, COALESCE(http_status,0)
            FROM outbox
           WHERE ts>=? AND (status NOT LIKE 'ok%' OR COALESCE(http_status,0) IN ({codes}))
        """.replace("{codes}", ",".join(str(x) for x in (codes or {0}))), (float(flash_start_ts),)).fetchall()

        for ts, key, text, status, http in rows:
            # 2) find the log news to understand the kind/event_id
            log = c.execute("""
              SELECT kind, COALESCE(event_id,0) FROM nudges_log
               WHERE key=? AND intent=? AND ts>=? ORDER BY ts DESC LIMIT 1
            """, (str(key), str(text), float(flash_start_ts)-300)).fetchone()
            if not log:
                continue
            kind, ev_id = str(log[0]), int(log[1] or 0)
            # 3) if there is already a pending for this key/intent, we do not duplicate it
            if _has_pending_for(str(key), str(text)):
                continue
            # 4) level retro according to the number of past files
            idx = min(len(sched)-1, max(0, _fails_count(str(key), str(text))-1))
            due_ts = now + sched[idx]*60

            # 5) create a synthetic event NoJesRetro with the entity of the previous event (if available)
            entity_id = "retry:"+str(key)
            if ev_id>0:
                ev = read_event(ev_id)
                if ev and ev.get("event_type"):
                    entity_id = str(ev.get("entity_id") or entity_id)
            retry_event_id = add_event("NudgesRetry", entity_id, now, {"intent": text, "key": key, "retry_idx": idx})

            # 6) enqueue
            cur2 = c.execute(
                "INSERT OR IGNORE INTO nudges_pending(event_id,created_ts,due_ts,key,kind,intent,status,reason) VALUES(?,?,?,?,?,?,?,?)",
                (int(retry_event_id), now, float(due_ts), str(key), str(kind), str(text), "new", "retry")
            )
            if int(cur2.rowcount or 0) > 0:
                requeued += 1

    return requeued