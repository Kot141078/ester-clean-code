# -*- coding: utf-8 -*-
"""
messaging/optin_store.py — ustoychivoe khranilische opt-in/nastroek/tishiny/inboksa (SQLite).

MOSTY:
- (Yavnyy) opt-in i prefs (rate/persona) + silence_until + outbound last_ts — edinyy istochnik pravdy.
- (Skrytyy #1) Tablitsa inbox dlya poslednikh vkhodyaschikh (dlya mini-inboksa v adminke).
- (Skrytyy #2) Avtosozdanie i bezopasnye korotkie tranzaktsii — bez blokirovok i pobochek.

ZEMNOY ABZATs:
My znaem, kto podpisan, kak chasto im mozhno pisat, kogda vklyuchen «tikhiy rezhim», i vidim poslednie vkhodyaschie — vse v odnom legkom fayle.

# c=a+b
"""
from __future__ import annotations

import os, sqlite3, time
from dataclasses import dataclass
from typing import Optional, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DDL = """
CREATE TABLE IF NOT EXISTS optin (
  key TEXT PRIMARY KEY,
  agree INTEGER NOT NULL,
  updated_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS prefs (
  key TEXT PRIMARY KEY,
  rate_per_h INTEGER NOT NULL,
  persona TEXT NOT NULL,
  updated_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS outbound (
  key TEXT PRIMARY KEY,
  last_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS silence (
  key TEXT PRIMARY KEY,
  until_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  channel TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  user_id TEXT,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inbox_ts ON inbox(ts DESC);
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
        conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)  # autocommit
        try:
            conn.execute("PRAGMA journal_mode=WAL" if prefer_wal else "PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    c = _open(prefer_wal=True)
    try:
        c.executescript(DDL)
        return c
    except sqlite3.OperationalError as e:
        # Some Windows runs leave broken WAL sidecars in test mode; heal and retry once.
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
            return c2
        except sqlite3.OperationalError:
            c2.close()
            return _memory_conn(db_path)

@dataclass
class Prefs:
    rate_per_h: int = 6
    persona: str = "gentle"

# ----- opt-in / prefs / outbound -----

def set_optin(key: str, agree: bool) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO optin(key,agree,updated_ts) VALUES(?,?,?)", (key, 1 if agree else 0, time.time()))

def get_optin(key: str) -> bool:
    with _conn() as c:
        row = c.execute("SELECT agree FROM optin WHERE key=?", (key,)).fetchone()
        return bool(row and int(row[0]) == 1)

def set_prefs(key: str, rate_per_h: int, persona: str) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO prefs(key,rate_per_h,persona,updated_ts) VALUES(?,?,?,?)",
                  (key, int(rate_per_h), persona, time.time()))

def get_prefs(key: str) -> Prefs:
    with _conn() as c:
        row = c.execute("SELECT rate_per_h, persona FROM prefs WHERE key=?", (key,)).fetchone()
        if not row:
            return Prefs()
        return Prefs(rate_per_h=int(row[0]), persona=str(row[1]))

def record_outbound(key: str) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO outbound(key,last_ts) VALUES(?,?)", (key, time.time()))

def last_outbound(key: str) -> float:
    with _conn() as c:
        row = c.execute("SELECT last_ts FROM outbound WHERE key=?", (key,)).fetchone()
        return float(row[0]) if row else 0.0

# ----- silence -----

def set_silence_until(key: str, until_ts: float) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO silence(key, until_ts) VALUES(?,?)", (key, float(until_ts)))

def clear_silence(key: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM silence WHERE key=?", (key,))

def get_silence_until(key: str) -> float:
    with _conn() as c:
        row = c.execute("SELECT until_ts FROM silence WHERE key=?", (key,)).fetchone()
        return float(row[0]) if row else 0.0

# ----- inbox -----

def inbox_add(ts: float, channel: str, chat_id: str, user_id: str | None, text: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO inbox(ts,channel,chat_id,user_id,text) VALUES(?,?,?,?,?)",
                  (float(ts), channel, chat_id, user_id, text))

def inbox_list(limit: int = 100) -> List[Tuple[int, float, str, str, Optional[str], str]]:
    with _conn() as c:
        rows = c.execute("SELECT id,ts,channel,chat_id,user_id,text FROM inbox ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [(int(r[0]), float(r[1]), str(r[2]), str(r[3]), (str(r[4]) if r[4] is not None else None), str(r[5])) for r in rows]

def inbox_clear(older_than_ts: float | None = None) -> int:
    with _conn() as c:
        if older_than_ts is None:
            cur = c.execute("DELETE FROM inbox")
            return int(cur.rowcount or 0)
        cur = c.execute("DELETE FROM inbox WHERE ts < ?", (float(older_than_ts),))
        return int(cur.rowcount or 0)

# ----- listing -----

def list_contacts(limit: int = 200) -> List[Tuple[str, bool, int, str, float, float]]:
    """
    Vozvraschaet spisok (key, agree, rate_per_h, persona, last_ts, silence_until)
    """
    with _conn() as c:
        q = """
        SELECT k.key,
               COALESCE(o.agree,0),
               COALESCE(p.rate_per_h,6),
               COALESCE(p.persona,'gentle'),
               COALESCE(b.last_ts,0),
               COALESCE(s.until_ts,0)
        FROM (SELECT key FROM optin
              UNION SELECT key FROM prefs
              UNION SELECT key FROM outbound
              UNION SELECT key FROM silence) k
        LEFT JOIN optin o   ON o.key=k.key
        LEFT JOIN prefs p   ON p.key=k.key
        LEFT JOIN outbound b ON b.key=k.key
        LEFT JOIN silence s  ON s.key=k.key
        ORDER BY COALESCE(b.last_ts,0) DESC
        LIMIT ?
        """
        return [(r[0], bool(r[1]), int(r[2]), str(r[3]), float(r[4]), float(r[5])) for r in c.execute(q, (limit,)).fetchall()]
