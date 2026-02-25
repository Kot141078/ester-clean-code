# -*- coding: utf-8 -*-
"""roles/edges.py - graf "affinnosti" mezhdu agentami (sovmestnye aktivnosti/upominaniya), komandnaya prigodnost.

MOSTY:
- (Yavnyy) add_edge(agents, ctx, w) i team_affinity(agents) → chislovoy bonus [0..1] dlya orkestratora.
- (Skrytyy #1) Zatukhanie reber po vremeni (ROLE_EDGE_DECAY) bez migratsiy i fonovykh dzhob — primenyaetsya pri chtenii/apdeyte.
- (Skrytyy #2) Integratsiya s suschestvuyuschey BD (MESSAGING_DB_PATH) i rolyami (agent_id - tot zhe, chto v nudges/roles).

ZEMNOY ABZATs:
Lyudi luchshe rabotayut s temi, s kem “priterlis”. My uchityvaem sovmestnye vylety/smeny/chaty - i daem myagkiy bonus takoy komande.

# c=a+b"""
from __future__ import annotations

import os, time, sqlite3, json
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DECAY = float(os.getenv("ROLE_EDGE_DECAY","0.98") or "0.98")  # /sutki

DDL = """
CREATE TABLE IF NOT EXISTS roles_edges(
  a TEXT NOT NULL,
  b TEXT NOT NULL,
  weight REAL NOT NULL,
  updated_ts REAL NOT NULL,
  context_json TEXT,
  PRIMARY KEY(a,b)
);
CREATE INDEX IF NOT EXISTS idx_roles_edges_updated ON roles_edges(updated_ts);
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

def _decay_weight(w: float, last_ts: float) -> float:
    days = max(0.0, (time.time() - float(last_ts))/86400.0)
    return float(w) * (DECAY ** days)

def add_edge(agents: List[str], context: Dict[str,Any] | None = None, weight: float = 1.0) -> int:
    """Usilivaet svyazi mezhdu vsemi parami agents (komplekt ≥2)."""
    if not agents or len(agents) < 2:
        return 0
    now = time.time()
    pairs = []
    for i in range(len(agents)):
        for j in range(i+1, len(agents)):
            a, b = sorted([str(agents[i]), str(agents[j])])
            pairs.append((a,b))
    n = 0
    ctx = json.dumps(context or {}, ensure_ascii=False)
    with _conn() as c:
        for a,b in pairs:
            row = c.execute("SELECT weight, updated_ts, COALESCE(context_json,'{}') FROM roles_edges WHERE a=? AND b=?", (a,b)).fetchone()
            if row:
                w0, ts0, ctx0 = float(row[0]), float(row[1]), row[2]
                w = _decay_weight(w0, ts0) + float(weight)
                # saves last context
                c.execute("UPDATE roles_edges SET weight=?, updated_ts=?, context_json=? WHERE a=? AND b=?",
                          (w, now, ctx, a, b))
            else:
                c.execute("INSERT INTO roles_edges(a,b,weight,updated_ts,context_json) VALUES(?,?,?,?,?)",
                          (a, b, float(weight), now, ctx))
            n += 1
    return n

def get_edge(a: str, b: str) -> Dict[str,Any]:
    a,b = sorted([str(a), str(b)])
    with _conn() as c:
        row = c.execute("SELECT weight, updated_ts FROM roles_edges WHERE a=? AND b=?", (a,b)).fetchone()
        if not row:
            return {"weight":0.0, "updated_ts":0.0}
        w = _decay_weight(float(row[0]), float(row[1]))
        return {"weight": w, "updated_ts": float(row[1])}

def team_affinity(agents: List[str]) -> float:
    """Returns ω0..1π: the normalized sum of pairwise weights."""
    ag = sorted(list({str(x) for x in (agents or [])}))
    if len(ag) < 2:
        return 0.0
    total = 0.0; pairs = 0
    for i in range(len(ag)):
        for j in range(i+1, len(ag)):
            pairs += 1
            total += get_edge(ag[i], ag[j])["weight"]
    # grubaya lognorm-normalizatsiya: schitaem, chto 3—5 sovmestnykh silnykh vzaimodeystviy ≈ 1.0
    return max(0.0, min(1.0, total / max(1.0, 5.0 * pairs)))
