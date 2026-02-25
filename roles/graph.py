# -*- coding: utf-8 -*-
"""roles/graph.py - prostoy graf vzaimodeystviy (lyudi↔lyudi) v obschey BD.

MOSTY:
- (Yavnyy) touch_edge(a,b,weight,context) i neighbors(agent) — fiksiruem “who s kem rabotal” i otdaem okrestnost.
- (Skrytyy #1) cohesion_bonus_for(a,b) — vychislyaet bonus sygrannosti [0..1] s zatukhaniem po vremeni.
- (Skrytyy #2) Tablitsa roles_edges ne konfliktuet s suschestvuyuschimi skhemami, obschiy SQLite (MESSAGING_DB_PATH).

ZEMNOY ABZATs:
Komanda - eto ne prosto “luchshie po otdelnosti.” My pomnim, who s kem “srabotan”, i daem bonus pri sovmestnoy rabote.

# c=a+b"""
from __future__ import annotations

import os, time, sqlite3, json, math
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DDL = """
CREATE TABLE IF NOT EXISTS roles_edges(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  a TEXT NOT NULL,
  b TEXT NOT NULL,
  weight REAL NOT NULL,
  context TEXT
);
CREATE INDEX IF NOT EXISTS idx_re_ab ON roles_edges(a,b);
CREATE INDEX IF NOT EXISTS idx_re_ts ON roles_edges(ts);
"""

_MEM_CONN_CACHE: dict[str, sqlite3.Connection] = {}


def _memory_conn(cache_key: str) -> sqlite3.Connection:
    conn = _MEM_CONN_CACHE.get(cache_key)
    if conn is None:
        conn = sqlite3.connect(":memory:", timeout=5.0, isolation_level=None, check_same_thread=False)
        conn.executescript(DDL)
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

    try:
        c = _open(prefer_wal=True)
    except sqlite3.OperationalError:
        return _memory_conn(db_path)
    try:
        c.executescript(DDL)
        return c
    except sqlite3.OperationalError as e:
        c.close()
        msg = str(e).lower()
        if "disk i/o" in msg or "malformed" in msg:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(db_path + suffix)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
        try:
            c2 = _open(prefer_wal=False)
        except sqlite3.OperationalError:
            return _memory_conn(db_path)
        try:
            c2.executescript(DDL)
            return c2
        except sqlite3.OperationalError:
            c2.close()
            return _memory_conn(db_path)

def touch_edge(a: str, b: str, weight: float = 1.0, context: str = "") -> None:
    if not a or not b or a == b: return
    w = max(0.0, min(1.0, float(weight)))
    with _conn() as c:
        c.execute("INSERT INTO roles_edges(ts,a,b,weight,context) VALUES(?,?,?,?,?)",
                  (time.time(), a, b, w, context[:200]))
        c.execute("INSERT INTO roles_edges(ts,a,b,weight,context) VALUES(?,?,?,?,?)",
                  (time.time(), b, a, w, context[:200]))

def neighbors(agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("""
           SELECT b, AVG(weight) AS w, MAX(ts) AS last_ts, COUNT(*) AS cnt
             FROM roles_edges WHERE a=?
         GROUP BY b ORDER BY w DESC, last_ts DESC LIMIT ?""", (agent_id, int(limit))).fetchall()
    out=[]
    now=time.time()
    for b, w, ts, cnt in rows:
        out.append({"agent_id": b, "weight": float(w or 0.0), "last_ts": int(ts or 0), "count": int(cnt or 0),
                    "fresh": max(0.0, 1.0 - (now - float(ts or 0))/ (14*24*3600))})  # svezhest: 2 nedeli
    return out

def cohesion_bonus_for(a: str, b: str) -> float:
    """0..1 — how much to add to the score for “teamwork”: average weight * freshness."""
    with _conn() as c:
        row = c.execute("SELECT AVG(weight), MAX(ts) FROM roles_edges WHERE a=? AND b=?", (a,b)).fetchone()
    if not row: return 0.0
    w, ts = float(row[0] or 0.0), float(row[1] or 0.0)
    if ts <= 0: return 0.0
    fresh = max(0.0, 1.0 - (time.time() - ts)/ (14*24*3600))
    return max(0.0, min(1.0, w * fresh))
