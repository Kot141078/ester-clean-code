# -*- coding: utf-8 -*-
"""modules/synergy/store.py - persistentnost Synergy: event-sourcing + audit hash-chain (SQLite).

MOSTY:
- (Yavnyy) Tablitsy: events (s khesh-tsepochkoy), plans (aktualnoe naznachenie po team_id), edits (redaktiruemyy kanal).
- (Skrytyy #1) Atomarnye tranzaktsii, WAL, idempotentnye klyuchi (request_id) dlya sobytiy odnogo zaprosa.
- (Skrytyy #2) Khuki dlya suschestvuyuschego orkestratora/ruchek: hook_assign_request/Result/Outcome — drop-in.

ZEMNOY ABZATs:
Daet vosproizvodimost i audit: kazhdoe naznachenie i ego iskhod popadaet v neizmenyaemuyu tsepochku sobytiy.
Esli chto-to poshlo ne tak - po tsepochke mozhno vosstanovit pravdu i plan na lyuboy moment vremeni.

# c=a+b"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ================== VSPOMOGATELNOE ==================

def _now_s() -> int:
    return int(time.time())

def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

def _conn_path() -> str:
    # Prioritet: SYNERGY_DB_PATH → SYNERGY_DB_URL (sqlite:///path)
    path = os.getenv("SYNERGY_DB_PATH")
    if path:
        return path
    url = os.getenv("SYNERGY_DB_URL", "sqlite:///data/ester.db")
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    if url.startswith("file:"):
        # podderzhka URI (journal_mode=WAL i pr.)
        return url  # sqlite3 umeet URI pri uri=True
    # fallback
    return url

# ==== Schema/Initialization ==================

_SCHEMA_SQL = """PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  team_id TEXT NOT NULL,
  type TEXT NOT NULL, -- AssignmentRequested|Planned|Applied|OutcomeReported|Edit
  payload TEXT NOT NULL, -- canonical JSON
  request_id TEXT, -- idempotentnost
  who TEXT, -- optsionalno: kto initsiiroval
  meta TEXT, -- optsionalno: metadannye zaprosa/kanala
  prev_hash TEXT, -- khesh predyduschego sobytiya v obschey tsepochke
  hash TEXT NOT NULL -- khesh tekuschego sobytiya: sha256(prev_hash|ts|team_id|type|sha256(payload)|request_id)
);
CREATE INDEX IF NOT EXISTS ix_events_team_ts ON events(team_id, ts);
CREATE INDEX IF NOT EXISTS ix_events_req ON events(request_id);

CREATE TABLE IF NOT EXISTS plans(
  team_id TEXT PRIMARY KEY,
  assigned TEXT NOT NULL, -- JSON dict {role: agent_id}
  trace_id TEXT,
  total REAL,
  penalty REAL,
  updated_ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS edits(
  edit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL,
  field TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  ts INTEGER NOT NULL,
  FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);"""

# ================== KLASS KhRANILISchA ==================

@dataclass
class Event:
    id: int
    ts: int
    team_id: str
    type: str
    payload: Dict[str, Any]
    request_id: Optional[str]
    who: Optional[str]
    meta: Optional[Dict[str, Any]]
    prev_hash: Optional[str]
    hash: str

@dataclass
class VerifyReport:
    ok: bool
    broken_at: Optional[int] = None
    reason: Optional[str] = None


class AssignmentStore:
    """Lightweight SGLite-side for event-sourcing Synergy.
    Thread safe via internal locking; connections are opened on demand."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or _conn_path()
        self._lock = threading.RLock()
        self._ensure_dir()
        self._init_schema()

    # ---------- bootstrap ----------
    def _connect(self) -> sqlite3.Connection:
        uri = self.path.startswith("file:")
        conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, uri=uri)
        conn.row_factory = sqlite3.Row
        if os.getenv("SYNERGY_DB_WAL", "1") == "1" and not uri:
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
            except Exception:
                pass
        return conn

    def _ensure_dir(self) -> None:
        if self.path.startswith("file:"):
            return
        d = os.path.dirname(self.path) or "."
        os.makedirs(d, exist_ok=True)

    def _init_schema(self) -> None:
        with self._connect() as c, self._lock:
            for stmt in _SCHEMA_SQL.strip().split(";"):
                s = stmt.strip()
                if s:
                    c.execute(s)

    # ---------- hash-chain ----------
    def _last_hash(self, c: sqlite3.Connection) -> Optional[str]:
        row = c.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
        return row["hash"] if row else None

    def _calc_hash(self, prev_hash: Optional[str], ts: int, team_id: str, typ: str, payload: Dict[str, Any], request_id: Optional[str]) -> str:
        body = _json_dumps(payload).encode("utf-8")
        h = f"{prev_hash or ''}|{ts}|{team_id}|{typ}|{_sha256_hex(body)}|{request_id or ''}"
        return _sha256_hex(h.encode("utf-8"))

    # ---------- events API ----------
    def record_event(
        self,
        team_id: str,
        typ: str,
        payload: Dict[str, Any],
        request_id: Optional[str] = None,
        who: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Event:
        ts = _now_s()
        meta = meta or {}
        with self._connect() as c, self._lock:
            prev = self._last_hash(c)
            h = self._calc_hash(prev, ts, team_id, typ, payload, request_id)
            cur = c.cursor()
            cur.execute(
                "INSERT INTO events(ts,team_id,type,payload,request_id,who,meta,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?,?)",
                (ts, team_id, typ, _json_dumps(payload), request_id, who, _json_dumps(meta), prev, h),
            )
            ev_id = cur.lastrowid
            row = c.execute("SELECT * FROM events WHERE id=?", (ev_id,)).fetchone()
        return self._row_to_event(row)

    def list_events(self, team_id: str, limit: int = 100, offset: int = 0) -> List[Event]:
        with self._connect() as c, self._lock:
            rows = c.execute(
                "SELECT * FROM events WHERE team_id=? ORDER BY id ASC LIMIT ? OFFSET ?",
                (team_id, int(limit), int(offset)),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def verify_chain(self, team_id: Optional[str] = None) -> VerifyReport:
        """Checks the continuity of the hash chain (within team_ids or globally)."""
        sql = "SELECT id,ts,team_id,type,payload,request_id,prev_hash,hash FROM events"
        if team_id:
            sql += "WHERE team_id=? "
        sql += "ORDER BY id ASC"
        args: Tuple[Any, ...] = (team_id,) if team_id else tuple()

        with self._connect() as c, self._lock:
            rows = c.execute(sql, args).fetchall()

        prev = None
        for r in rows:
            payload = json.loads(r["payload"])
            expected = self._calc_hash(prev, r["ts"], r["team_id"], r["type"], payload, r["request_id"])
            if expected != r["hash"]:
                return VerifyReport(ok=False, broken_at=int(r["id"]), reason="hash_mismatch")
            prev = r["hash"]
        return VerifyReport(ok=True)

    # ---------- plans (upsert aktualnogo sostoyaniya) ----------
    def upsert_plan(self, team_id: str, assigned: Dict[str, str], trace_id: Optional[str], total: Optional[float], penalty: Optional[float]) -> None:
        with self._connect() as c, self._lock:
            c.execute(
                "INSERT INTO plans(team_id,assigned,trace_id,total,penalty,updated_ts) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(team_id) DO UPDATE SET assigned=excluded.assigned, trace_id=excluded.trace_id, total=excluded.total, penalty=excluded.penalty, updated_ts=excluded.updated_ts",
                (team_id, _json_dumps(assigned), trace_id, total, penalty, _now_s()),
            )

    def get_latest_plan(self, team_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as c, self._lock:
            row = c.execute("SELECT * FROM plans WHERE team_id=?", (team_id,)).fetchone()
        if not row:
            return None
        return {
            "team_id": row["team_id"],
            "assigned": json.loads(row["assigned"]),
            "trace_id": row["trace_id"],
            "total": row["total"],
            "penalty": row["penalty"],
            "updated_ts": row["updated_ts"],
        }

    # ---------- redaktiruemyy kanal ----------
    def record_edit(self, event_id: int, field: str, old_value: Any, new_value: Any) -> int:
        with self._connect() as c, self._lock:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO edits(event_id,field,old_value,new_value,ts) VALUES(?,?,?,?,?)",
                (event_id, field, _json_dumps(old_value), _json_dumps(new_value), _now_s()),
            )
            return int(cur.lastrowid)

    def list_edits(self, event_id: int) -> List[Dict[str, Any]]:
        with self._connect() as c, self._lock:
            rows = c.execute("SELECT * FROM edits WHERE event_id=? ORDER BY edit_id ASC", (event_id,)).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "edit_id": r["edit_id"],
                    "event_id": r["event_id"],
                    "field": r["field"],
                    "old_value": json.loads(r["old_value"]) if r["old_value"] else None,
                    "new_value": json.loads(r["new_value"]) if r["new_value"] else None,
                    "ts": r["ts"],
                }
            )
        return out

    # ---------- utility integratsii (drop-in) ----------
    def hook_assign_request(self, team_id: str, roles: List[str], overrides: Dict[str, str], request_id: Optional[str] = None, who: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Event:
        """Record the fact of the assignment request (before calling the orchestrator)."""
        payload = {"roles": roles, "overrides": overrides}
        return self.record_event(team_id, "AssignmentRequested", payload, request_id=request_id, who=who, meta=meta)

    def hook_assign_result(self, team_id: str, result: Dict[str, Any], request_id: Optional[str] = None, who: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Event:
        """Write down the plan, save the current snapshot.
        Expects a result in the format assign_v2(...)."""
        assigned = dict(result.get("assigned") or {})
        total = float(result.get("total") or 0.0)
        penalty = float(result.get("penalty") or 0.0)
        trace_id = str(result.get("trace_id") or "")
        self.upsert_plan(team_id, assigned, trace_id, total, penalty)
        ev = self.record_event(team_id, "Planned", {"result": result}, request_id=request_id, who=who, meta=meta)
        return ev

    def hook_apply(self, team_id: str, plan: Dict[str, Any], request_id: Optional[str] = None, who: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Event:
        """Record the application of the plan (for example, when the assignments actually took effect in external systems)."""
        ev = self.record_event(team_id, "Applied", {"plan": plan}, request_id=request_id, who=who, meta=meta)
        return ev

    def hook_outcome(self, team_id: str, outcome: str, notes: str = "", request_id: Optional[str] = None, who: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Event:
        """The final outcome of the operation."""
        ev = self.record_event(team_id, "OutcomeReported", {"outcome": outcome, "notes": notes}, request_id=request_id, who=who, meta=meta)
        return ev

    # ---------- reconstruction based on events ----------
    def rebuild_plan_from_events(self, team_id: str) -> Dict[str, Any]:
        """Walks through command events and restores the last assignment and known attributes."""
        events = self.list_events(team_id, limit=10_000, offset=0)
        last_result: Optional[Dict[str, Any]] = None
        last_trace: Optional[str] = None
        total = 0.0
        penalty = 0.0
        for e in events:
            if e.type == "Planned":
                r = e.payload.get("result") or {}
                last_result = dict(r.get("assigned") or {})
                total = float(r.get("total") or 0.0)
                penalty = float(r.get("penalty") or 0.0)
                last_trace = r.get("trace_id")
        return {"team_id": team_id, "assigned": last_result or {}, "trace_id": last_trace, "total": total, "penalty": penalty}

    # ---------- utility ----------
    @staticmethod
    def default() -> "AssignmentStore":
        return AssignmentStore()

    @staticmethod
    def _row_to_event(r: sqlite3.Row) -> Event:
        return Event(
            id=int(r["id"]),
            ts=int(r["ts"]),
            team_id=str(r["team_id"]),
            type=str(r["type"]),
            payload=json.loads(r["payload"]),
            request_id=r["request_id"],
            who=r["who"],
            meta=json.loads(r["meta"]) if r["meta"] else None,
            prev_hash=r["prev_hash"],
            hash=r["hash"],
        )

# End of module