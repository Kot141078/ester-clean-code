# -*- coding: utf-8 -*-
"""
nudges/store.py — khranilische sobytiy/ocheredi/logov + eskalatsii i metriki (rasshireno).

MOSTY:
- (Yavnyy) list_escalation_keys() — otdaet spisok vsekh kontaktnykh klyuchey, privyazannykh k eskalatsionnym tegam.
- (Skrytyy #1) board_metrics() dopolnen 'overdue_due' (schitalsya ranee) — prigoden dlya SLO-alertov.
- (Skrytyy #2) DDL neizmenen po smyslu; bootstrap forwarder_state sokhranyaetsya.

ZEMNOY ABZATs:
Znaem «kuda eskalirovat» i «kak goryacho seychas» — mozhno triggerit alerty i berezhno ubirat shum posle eskalatsii.

# c=a+b
"""
from __future__ import annotations

import os, sqlite3, time, json
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DDL = """
CREATE TABLE IF NOT EXISTS nudges_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  event_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  received_ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ne_entity ON nudges_events(entity_id);
CREATE INDEX IF NOT EXISTS idx_ne_ts ON nudges_events(ts);

CREATE TABLE IF NOT EXISTS nudges_pending (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL,
  created_ts REAL NOT NULL,
  due_ts REAL NOT NULL,
  key TEXT NOT NULL,
  kind TEXT NOT NULL,
  intent TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT,
  UNIQUE(event_id, key, kind, intent) ON CONFLICT IGNORE
);
CREATE INDEX IF NOT EXISTS idx_np_due ON nudges_pending(due_ts);
CREATE INDEX IF NOT EXISTS idx_np_status ON nudges_pending(status);

CREATE TABLE IF NOT EXISTS nudges_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  key TEXT NOT NULL,
  kind TEXT NOT NULL,
  intent TEXT NOT NULL,
  status TEXT NOT NULL,
  http_status INTEGER,
  event_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_nl_ts ON nudges_log(ts DESC);

CREATE TABLE IF NOT EXISTS nudges_recipients (
  agent_id TEXT PRIMARY KEY,
  contact_key TEXT NOT NULL,
  updated_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS nudges_escalations (
  tag TEXT PRIMARY KEY,
  contact_key TEXT NOT NULL,
  updated_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS nudges_forwarder_state(
  id INTEGER PRIMARY KEY CHECK (id=1),
  last_ts REAL NOT NULL
);
"""

_MEM_CONN_CACHE: dict[str, sqlite3.Connection] = {}


def _memory_conn(cache_key: str) -> sqlite3.Connection:
    conn = _MEM_CONN_CACHE.get(cache_key)
    if conn is None:
        conn = sqlite3.connect(":memory:", timeout=5.0, isolation_level=None, check_same_thread=False)
        conn.executescript(DDL)
        conn.execute("INSERT OR IGNORE INTO nudges_forwarder_state(id,last_ts) VALUES(1,0)")
        _MEM_CONN_CACHE[cache_key] = conn
    return conn

def _conn() -> sqlite3.Connection:
    db_path = os.getenv("MESSAGING_DB_PATH", "data/messaging.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    def _open(prefer_wal: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL" if prefer_wal else "PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    c = _open(prefer_wal=True)
    try:
        c.executescript(DDL)
        c.execute("INSERT OR IGNORE INTO nudges_forwarder_state(id,last_ts) VALUES(1,0)")
        return c
    except sqlite3.OperationalError as e:
        c.close()
        msg = str(e).lower()
        if "disk i/o" not in msg and "malformed" not in msg:
            raise
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(db_path + suffix)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        c2 = _open(prefer_wal=False)
        try:
            c2.executescript(DDL)
            c2.execute("INSERT OR IGNORE INTO nudges_forwarder_state(id,last_ts) VALUES(1,0)")
            return c2
        except sqlite3.OperationalError:
            c2.close()
            return _memory_conn(db_path)

# ----- bazovye operatsii (bez izmeneniy v signaturakh) -----

def add_event(event_type: str, entity_id: str, ts: float, payload: Dict[str, Any]) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO nudges_events(ts,event_type,entity_id,payload_json,received_ts) VALUES(?,?,?,?,?)",
            (float(ts or time.time()), event_type, entity_id, json.dumps(payload, ensure_ascii=False), time.time())
        )
        return int(cur.lastrowid)

def read_event(event_id: int) -> Dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT id,ts,event_type,entity_id,payload_json FROM nudges_events WHERE id=?", (int(event_id),)).fetchone()
        if not row: return None
        return {"id": int(row[0]), "ts": float(row[1]), "event_type": str(row[2]), "entity_id": str(row[3]),
                "payload": json.loads(row[4] or "{}")}

def map_agent(agent_id: str, contact_key: str) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO nudges_recipients(agent_id,contact_key,updated_ts) VALUES(?,?,?)",
                  (agent_id, contact_key, time.time()))

def unmap_agent(agent_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM nudges_recipients WHERE agent_id=?", (agent_id,))

def get_contact_key(agent_id: str) -> str | None:
    with _conn() as c:
        r = c.execute("SELECT contact_key FROM nudges_recipients WHERE agent_id=?", (agent_id,)).fetchone()
        return str(r[0]) if r else None

def list_mappings(limit: int = 500) -> List[Tuple[str, str, float]]:
    with _conn() as c:
        rows = c.execute("SELECT agent_id, contact_key, updated_ts FROM nudges_recipients ORDER BY updated_ts DESC LIMIT ?", (int(limit),)).fetchall()
        return [(str(r[0]), str(r[1]), float(r[2])) for r in rows]

def map_escalation(tag: str, contact_key: str) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO nudges_escalations(tag,contact_key,updated_ts) VALUES(?,?,?)",
                  (tag, contact_key, time.time()))

def get_escalation(tag: str) -> str | None:
    with _conn() as c:
        r = c.execute("SELECT contact_key FROM nudges_escalations WHERE tag=?", (tag,)).fetchone()
        return str(r[0]) if r else None

def list_escalations(limit: int = 200) -> List[Tuple[str, str, float]]:
    with _conn() as c:
        rows = c.execute("SELECT tag, contact_key, updated_ts FROM nudges_escalations ORDER BY updated_ts DESC LIMIT ?", (int(limit),)).fetchall()
        return [(str(r[0]), str(r[1]), float(r[2])) for r in rows]

def list_escalation_keys() -> List[str]:
    with _conn() as c:
        rows = c.execute("SELECT contact_key FROM nudges_escalations").fetchall()
        return [str(r[0]) for r in rows]

def enqueue(event_id: int, due_ts: float, key: str, kind: str, intent: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO nudges_pending(event_id,created_ts,due_ts,key,kind,intent,status,reason) VALUES(?,?,?,?,?,?,?,?)",
            (int(event_id), time.time(), float(due_ts), key, kind, intent, "new", "")
        )
        return int(cur.lastrowid or 0)

def list_pending(limit: int = 200, due_only: bool = True) -> List[Tuple[int, int, float, float, str, str, str, str]]:
    sql = "SELECT id, event_id, created_ts, due_ts, key, kind, intent, status FROM nudges_pending"
    if due_only:
        sql += " WHERE status='new' AND due_ts<=?"
        args = (time.time(),)
    else:
        sql += " WHERE status='new'"
        args = ()
    sql += " ORDER BY due_ts ASC, id ASC LIMIT ?"
    args = args + (int(limit),)
    with _conn() as c:
        rows = c.execute(sql, args).fetchall()
        return [(int(r[0]), int(r[1]), float(r[2]), float(r[3]), str(r[4]), str(r[5]), str(r[6]), str(r[7])) for r in rows]

def mark(pending_id: int, status: str, reason: str = "") -> None:
    with _conn() as c:
        c.execute("UPDATE nudges_pending SET status=?, reason=? WHERE id=?", (status, reason, int(pending_id)))

def skip_pending_by_entity(entity_id: str, reason: str = "outcome") -> int:
    with _conn() as c:
        cur = c.execute("""
            UPDATE nudges_pending
               SET status='skipped', reason=?
             WHERE status='new'
               AND event_id IN (SELECT id FROM nudges_events WHERE entity_id=?)
        """, (f"skipped:{reason}", entity_id))
        return int(cur.rowcount or 0)

def log_send(key: str, kind: str, intent: str, status: str, http_status: int | None, event_id: int | None) -> None:
    with _conn() as c:
        c.execute("INSERT INTO nudges_log(ts,key,kind,intent,status,http_status,event_id) VALUES(?,?,?,?,?,?,?)",
                  (time.time(), key, kind, intent, status, int(http_status or 0), event_id))

def list_log(limit: int = 200) -> List[Tuple[int, float, str, str, str, str, int, int]]:
    with _conn() as c:
        rows = c.execute("SELECT id,ts,key,kind,intent,status,http_status,event_id FROM nudges_log ORDER BY ts DESC LIMIT ?", (int(limit),)).fetchall()
        return [(int(r[0]), float(r[1]), str(r[2]), str(r[3]), str(r[4]), str(r[5]), int(r[6] or 0), int(r[7] or 0)) for r in rows]

def board_metrics(now_ts: float | None = None) -> Dict[str, Any]:
    now_ts = float(now_ts or time.time())
    day_ago = now_ts - 86400
    with _conn() as c:
        pending_total = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new'").fetchone()[0]
        pending_due   = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new' AND due_ts<=?", (now_ts,)).fetchone()[0]
        overdue_due   = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new' AND due_ts<?", (now_ts,)).fetchone()[0]
        sent_24h      = c.execute("SELECT COUNT(*) FROM nudges_log WHERE ts>=? AND status LIKE 'ok%'", (day_ago,)).fetchone()[0]
        fail_24h      = c.execute("SELECT COUNT(*) FROM nudges_log WHERE ts>=? AND status NOT LIKE 'ok%'", (day_ago,)).fetchone()[0]
        closed_reasons = dict(c.execute("SELECT reason, COUNT(*) FROM nudges_pending WHERE status!='new' GROUP BY reason").fetchall())
    return {
        "pending_total": int(pending_total),
        "pending_due": int(pending_due),
        "overdue_due": int(overdue_due),
        "sent_24h": int(sent_24h),
        "fail_24h": int(fail_24h),
        "closed_reasons": {str(k or ""): int(v) for k,v in closed_reasons.items()},
        "ts": int(now_ts),
    }
