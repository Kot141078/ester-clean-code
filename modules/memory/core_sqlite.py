# -*- coding: utf-8 -*-
"""
Sidecar SQLite memory core for safe migration away from monolithic memory.json.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_LOG = logging.getLogger(__name__)
_WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]+")
_CORE_LOCK = threading.RLock()
_CORE_SINGLETON: "MemoryCore | None" = None


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in ("1", "true", "yes", "on", "y", "да")


def _now_ts() -> int:
    return int(time.time())


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(raw: str, default_rel: str) -> Path:
    value = (raw or "").strip()
    if value:
        p = Path(value)
        if not p.is_absolute():
            p = _project_root() / value
        return p.resolve()
    return (_project_root() / default_rel).resolve()


def _default_db_path() -> Path:
    return _resolve_path(os.getenv("ESTER_MEMORY_CORE_PATH", ""), "data/memory_core/ester_memory.sqlite")


def _default_shadow_log() -> Path:
    return _resolve_path(os.getenv("ESTER_MEMORY_CORE_SHADOW_LOG", ""), "data/memory_core/shadow_compare.jsonl")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return "{}"


def _json_loads(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _coerce_ts(value: Any, default: Optional[int] = None) -> int:
    if default is None:
        default = _now_ts()
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _clip(text: str, limit: int = 240) -> str:
    txt = str(text or "").strip().replace("\r", " ").replace("\n", " ")
    if len(txt) <= limit:
        return txt
    return txt[: max(0, limit - 1)].rstrip() + "…"


def _normalize_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k in ("chat", "conversation"):
        return "dialog"
    if k in ("docsummary", "summary_doc"):
        return "doc_summary"
    return k or "fact"


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def _match_query(query: str) -> str:
    toks = _tokenize(query)
    if not toks:
        return ""
    quoted = ['"' + t.replace('"', '""') + '"' for t in toks[:16]]
    return " OR ".join(quoted)


def _stable_key(*parts: Any) -> str:
    payload = "\n".join(str(p or "") for p in parts)
    return hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{_stable_key(*parts)[:24]}"


def _calc_score(rank: Any, weight: float = 1.0, boost: float = 1.0) -> float:
    try:
        val = abs(float(rank))
    except Exception:
        val = 100.0
    return max(0.0001, float(weight) * float(boost) / (1.0 + val))


def _parse_bool(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0
    raw = str(value or "").strip().lower()
    return 1 if raw in ("1", "true", "yes", "on", "y", "да") else 0


def _default_import_paths() -> Dict[str, Path]:
    root = _project_root()
    return {
        "snapshot": root / "data" / "memory" / "memory.json",
        "clean_memory": root / "data" / "passport" / "clean_memory.jsonl",
        "journal": root / "data" / "memory" / "journal_events.jsonl",
        "anchor": root / "data" / "passport" / "anchor.txt",
        "core_facts": root / "data" / "passport" / "core_facts.txt",
        "identity_dynamic": root / "data" / "passport" / "identity_dynamic.json",
    }


def core_enabled() -> bool:
    return _env_bool("ESTER_MEMORY_CORE_ENABLED", True)


def dual_write_enabled() -> bool:
    return _env_bool("ESTER_MEMORY_CORE_DUAL_WRITE", True)


def read_cutover_enabled() -> bool:
    return _env_bool("ESTER_MEMORY_CORE_READ_CUTOVER", False)


def shadow_read_enabled() -> bool:
    return _env_bool("ESTER_MEMORY_CORE_SHADOW_READ", False)


class MemoryCore:
    def __init__(self, path: Optional[str] = None) -> None:
        resolved = _resolve_path(path or "", "data/memory_core/ester_memory.sqlite")
        _ensure_parent(resolved)
        self.path = resolved
        self.shadow_log_path = _default_shadow_log()
        _ensure_parent(self.shadow_log_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), timeout=30.0, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._has_fts = False
        self._setup()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def _setup(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
                self._conn.execute("PRAGMA foreign_keys=ON;")
                self._conn.execute("PRAGMA temp_store=MEMORY;")
                self._conn.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_ts INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS import_runs (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    started_ts INTEGER NOT NULL,
                    finished_ts INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    stats_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    event_kind TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    scope TEXT NOT NULL DEFAULT 'global',
                    legacy_id TEXT,
                    source_ref TEXT NOT NULL DEFAULT '',
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    raw_hash TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source ON events(source_name, source_key);
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);

                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    event_id TEXT,
                    item_kind TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    text TEXT NOT NULL,
                    salience REAL NOT NULL DEFAULT 0.0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    scope TEXT NOT NULL DEFAULT 'global',
                    source TEXT NOT NULL DEFAULT '',
                    created_ts INTEGER NOT NULL,
                    last_access_ts INTEGER NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    pin INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    legacy_id TEXT,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE SET NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_items_source ON memory_items(source_name, source_key);
                CREATE INDEX IF NOT EXISTS idx_memory_items_kind ON memory_items(item_kind, created_ts DESC);
                CREATE INDEX IF NOT EXISTS idx_memory_items_layer ON memory_items(layer, created_ts DESC);
                """
            )
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    memory_item_id TEXT,
                    fact_kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object_text TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    ts INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(memory_item_id) REFERENCES memory_items(id) ON DELETE SET NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_facts_source ON facts(source_name, source_key);
                CREATE INDEX IF NOT EXISTS idx_facts_ts ON facts(ts DESC);

                CREATE TABLE IF NOT EXISTS identity_items (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    label TEXT NOT NULL,
                    text TEXT NOT NULL,
                    priority REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT '',
                    created_ts INTEGER NOT NULL,
                    updated_ts INTEGER NOT NULL,
                    meta_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_source ON identity_items(source_name, source_key);
                CREATE INDEX IF NOT EXISTS idx_identity_priority ON identity_items(priority DESC, updated_ts DESC);
                """
            )
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    started_ts INTEGER NOT NULL,
                    ended_ts INTEGER NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.0,
                    text TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL DEFAULT '',
                    meta_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_episodes_source ON episodes(source_name, source_key);
                CREATE INDEX IF NOT EXISTS idx_episodes_time ON episodes(ended_ts DESC);

                CREATE TABLE IF NOT EXISTS summaries (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    period TEXT NOT NULL,
                    started_ts INTEGER NOT NULL,
                    ended_ts INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    meta_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_summaries_source ON summaries(source_name, source_key);
                CREATE INDEX IF NOT EXISTS idx_summaries_period ON summaries(period, ended_ts DESC);
                """
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value, updated_ts) VALUES (?, ?, ?)",
                ("schema_version", "1", _now_ts()),
            )
            self._has_fts = self._ensure_fts()

    def _ensure_fts(self) -> bool:
        try:
            self._create_fts("events", ["text", "source", "event_kind"])
            self._create_fts("memory_items", ["text", "item_kind", "layer"])
            self._create_fts("identity_items", ["label", "text"])
            self._create_fts("episodes", ["text", "summary", "source"])
            self._create_fts("summaries", ["text", "period"])
            self._create_fts("facts", ["subject", "predicate", "object_text"])
            return True
        except Exception as exc:
            _LOG.warning("memory core FTS disabled: %s", exc)
            return False

    def _create_fts(self, table: str, columns: List[str]) -> None:
        fts = f"{table}_fts"
        cols_sql = ", ".join(columns)
        new_cols = ", ".join(f"new.{c}" for c in columns)
        old_cols = ", ".join(f"old.{c}" for c in columns)
        with self._lock:
            self._conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {fts}
                USING fts5(
                    {cols_sql},
                    content='{table}',
                    content_rowid='rowid',
                    tokenize='unicode61'
                );
                """
            )
            self._conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_ai AFTER INSERT ON {table} BEGIN
                    INSERT INTO {fts}(rowid, {cols_sql}) VALUES (new.rowid, {new_cols});
                END;
                """
            )
            self._conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_ad AFTER DELETE ON {table} BEGIN
                    INSERT INTO {fts}({fts}, rowid, {cols_sql}) VALUES('delete', old.rowid, {old_cols});
                END;
                """
            )
            self._conn.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_au AFTER UPDATE ON {table} BEGIN
                    INSERT INTO {fts}({fts}, rowid, {cols_sql}) VALUES('delete', old.rowid, {old_cols});
                    INSERT INTO {fts}(rowid, {cols_sql}) VALUES (new.rowid, {new_cols});
                END;
                """
            )

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            self._conn.execute(sql, tuple(params))

    def _query(self, sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchall()

    def _classify_item(self, kind: str, text: str, meta: Dict[str, Any], legacy_record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        kind_n = _normalize_kind(kind)
        text_n = str(text or "").strip()
        source = str(meta.get("source") or "").lower()
        layer = str(meta.get("layer") or "").strip().lower()
        pin = bool(meta.get("pin")) or kind_n in {"fact", "goal", "doc", "doc_summary"}
        scope = str(meta.get("scope") or "global")
        technical = (
            kind_n == "trace"
            or text_n.startswith("[")
            or source in {"memory_boot", "memory_backup", "discovery_loader", "actions_discovery"}
            or bool((legacy_record or {}).get("dropped"))
        )
        salience = 0.2
        confidence = 0.5
        promote = False

        if kind_n in {"fact", "goal", "doc", "doc_summary"}:
            promote = True
            salience = 0.95 if pin else 0.85
            confidence = 0.9
            layer = layer or "canonical"
        elif kind_n == "summary":
            promote = True
            salience = 0.8
            confidence = 0.8
            layer = layer or "derived"
        elif kind_n == "dream":
            promote = True
            salience = 0.55
            confidence = 0.55
            layer = layer or "derived"
        elif kind_n in {"dialog", "event"}:
            salience = 0.5 if not technical else 0.12
            confidence = 0.65 if not technical else 0.35
            promote = (not technical and len(text_n) >= 40) or source in {"telegram", "web", "chat", "chat_api"}
            layer = layer or "episodic"
        else:
            salience = 0.6 if pin else 0.4
            confidence = 0.6
            promote = pin or len(text_n) >= 80
            layer = layer or "canonical"

        if technical and not pin and kind_n not in {"summary", "dream"}:
            promote = False

        return {
            "kind": kind_n,
            "layer": layer or "canonical",
            "pin": 1 if pin else 0,
            "scope": scope or "global",
            "salience": float(salience),
            "confidence": float(confidence),
            "promote": bool(promote),
        }

    def _upsert_event(
        self,
        *,
        source_name: str,
        source_key: str,
        ts: int,
        event_kind: str,
        role: str,
        text: str,
        source: str,
        scope: str,
        legacy_id: str,
        source_ref: str,
        meta: Dict[str, Any],
    ) -> str:
        eid = _stable_id("evt", source_name, source_key)
        raw_hash = _stable_key(source_name, source_key, ts, event_kind, text, source, scope, _json_dumps(meta))
        self._execute(
            """
            INSERT INTO events(
                id, source_name, source_key, ts, event_kind, role, text,
                source, scope, legacy_id, source_ref, meta_json, raw_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_key) DO UPDATE SET
                ts=excluded.ts,
                event_kind=excluded.event_kind,
                role=excluded.role,
                text=excluded.text,
                source=excluded.source,
                scope=excluded.scope,
                legacy_id=COALESCE(events.legacy_id, excluded.legacy_id),
                source_ref=excluded.source_ref,
                meta_json=excluded.meta_json,
                raw_hash=excluded.raw_hash
            """,
            (
                eid,
                source_name,
                source_key,
                int(ts),
                event_kind,
                role,
                text,
                source,
                scope,
                legacy_id,
                source_ref,
                _json_dumps(meta),
                raw_hash,
            ),
        )
        return eid

    def _upsert_memory_item(
        self,
        *,
        source_name: str,
        source_key: str,
        event_id: Optional[str],
        item_kind: str,
        layer: str,
        text: str,
        salience: float,
        confidence: float,
        scope: str,
        source: str,
        created_ts: int,
        pin: int,
        legacy_id: str,
        meta: Dict[str, Any],
    ) -> str:
        mid = _stable_id("mem", source_name, source_key)
        self._execute(
            """
            INSERT INTO memory_items(
                id, source_name, source_key, event_id, item_kind, layer, text,
                salience, confidence, scope, source, created_ts, last_access_ts,
                access_count, pin, active, legacy_id, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_key) DO UPDATE SET
                event_id=COALESCE(excluded.event_id, memory_items.event_id),
                item_kind=excluded.item_kind,
                layer=excluded.layer,
                text=excluded.text,
                salience=excluded.salience,
                confidence=excluded.confidence,
                scope=excluded.scope,
                source=excluded.source,
                pin=excluded.pin,
                active=1,
                legacy_id=COALESCE(memory_items.legacy_id, excluded.legacy_id),
                meta_json=excluded.meta_json
            """,
            (
                mid,
                source_name,
                source_key,
                event_id,
                item_kind,
                layer,
                text,
                float(salience),
                float(confidence),
                scope,
                source,
                int(created_ts),
                int(created_ts),
                0,
                int(pin),
                1,
                legacy_id,
                _json_dumps(meta),
            ),
        )
        return mid

    def _upsert_fact(
        self,
        *,
        source_name: str,
        source_key: str,
        memory_item_id: Optional[str],
        fact_kind: str,
        subject: str,
        predicate: str,
        object_text: str,
        confidence: float,
        ts: int,
        source: str,
        meta: Dict[str, Any],
    ) -> str:
        fid = _stable_id("fact", source_name, source_key)
        self._execute(
            """
            INSERT INTO facts(
                id, source_name, source_key, memory_item_id, fact_kind, subject,
                predicate, object_text, confidence, ts, source, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_key) DO UPDATE SET
                memory_item_id=COALESCE(excluded.memory_item_id, facts.memory_item_id),
                fact_kind=excluded.fact_kind,
                subject=excluded.subject,
                predicate=excluded.predicate,
                object_text=excluded.object_text,
                confidence=excluded.confidence,
                ts=excluded.ts,
                source=excluded.source,
                meta_json=excluded.meta_json
            """,
            (
                fid,
                source_name,
                source_key,
                memory_item_id,
                fact_kind,
                subject,
                predicate,
                object_text,
                float(confidence),
                int(ts),
                source,
                _json_dumps(meta),
            ),
        )
        return fid

    def _upsert_identity_item(
        self,
        *,
        source_name: str,
        source_key: str,
        label: str,
        text: str,
        priority: float,
        source: str,
        created_ts: int,
        meta: Dict[str, Any],
    ) -> str:
        iid = _stable_id("iden", source_name, source_key)
        self._execute(
            """
            INSERT INTO identity_items(
                id, source_name, source_key, label, text, priority, source,
                created_ts, updated_ts, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_key) DO UPDATE SET
                label=excluded.label,
                text=excluded.text,
                priority=excluded.priority,
                source=excluded.source,
                updated_ts=excluded.updated_ts,
                meta_json=excluded.meta_json
            """,
            (
                iid,
                source_name,
                source_key,
                label,
                text,
                float(priority),
                source,
                int(created_ts),
                int(created_ts),
                _json_dumps(meta),
            ),
        )
        return iid

    def _upsert_episode(
        self,
        *,
        source_name: str,
        source_key: str,
        started_ts: int,
        ended_ts: int,
        importance: float,
        text: str,
        summary: str,
        source: str,
        source_ref: str,
        meta: Dict[str, Any],
    ) -> str:
        eid = _stable_id("epi", source_name, source_key)
        self._execute(
            """
            INSERT INTO episodes(
                id, source_name, source_key, started_ts, ended_ts, importance,
                text, summary, source, source_ref, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_key) DO UPDATE SET
                started_ts=excluded.started_ts,
                ended_ts=excluded.ended_ts,
                importance=excluded.importance,
                text=excluded.text,
                summary=excluded.summary,
                source=excluded.source,
                source_ref=excluded.source_ref,
                meta_json=excluded.meta_json
            """,
            (
                eid,
                source_name,
                source_key,
                int(started_ts),
                int(ended_ts),
                float(importance),
                text,
                summary,
                source,
                source_ref,
                _json_dumps(meta),
            ),
        )
        return eid

    def _upsert_summary(
        self,
        *,
        source_name: str,
        source_key: str,
        period: str,
        started_ts: int,
        ended_ts: int,
        text: str,
        source: str,
        meta: Dict[str, Any],
    ) -> str:
        sid = _stable_id("sum", source_name, source_key)
        self._execute(
            """
            INSERT INTO summaries(
                id, source_name, source_key, period, started_ts, ended_ts, text, source, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_key) DO UPDATE SET
                period=excluded.period,
                started_ts=excluded.started_ts,
                ended_ts=excluded.ended_ts,
                text=excluded.text,
                source=excluded.source,
                meta_json=excluded.meta_json
            """,
            (
                sid,
                source_name,
                source_key,
                period,
                int(started_ts),
                int(ended_ts),
                text,
                source,
                _json_dumps(meta),
            ),
        )
        return sid

    def write_memory_add(
        self,
        kind: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        legacy_record: Optional[Dict[str, Any]] = None,
        source_ref: str = "modules.memory.facade",
    ) -> Dict[str, Any]:
        meta_in = dict(meta or {})
        legacy = dict(legacy_record or {})
        source_key = str(legacy.get("id") or uuid.uuid4().hex)
        ts = _coerce_ts(legacy.get("ts") or meta_in.get("ts"))
        source = str(meta_in.get("source") or "memory_add")
        role = str(meta_in.get("role") or "")
        spec = self._classify_item(kind, text, meta_in, legacy)
        event_id = self._upsert_event(
            source_name="legacy_store",
            source_key=source_key,
            ts=ts,
            event_kind=spec["kind"],
            role=role,
            text=str(text or ""),
            source=source,
            scope=spec["scope"],
            legacy_id=source_key,
            source_ref=source_ref,
            meta={**meta_in, "legacy_drop_reason": legacy.get("drop_reason", "")},
        )
        out: Dict[str, Any] = {"ok": True, "event_id": event_id, "memory_item_id": None, "promoted": False}
        if not spec["promote"]:
            return out

        memory_item_id = self._upsert_memory_item(
            source_name="legacy_store",
            source_key=source_key,
            event_id=event_id,
            item_kind=spec["kind"],
            layer=spec["layer"],
            text=str(text or ""),
            salience=spec["salience"],
            confidence=spec["confidence"],
            scope=spec["scope"],
            source=source,
            created_ts=ts,
            pin=spec["pin"],
            legacy_id=source_key,
            meta=meta_in,
        )
        out["memory_item_id"] = memory_item_id
        out["promoted"] = True

        if spec["kind"] in {"fact", "goal", "doc", "doc_summary"}:
            self._upsert_fact(
                source_name="legacy_fact",
                source_key=source_key,
                memory_item_id=memory_item_id,
                fact_kind=spec["kind"],
                subject=str(meta_in.get("subject") or "memory"),
                predicate=str(meta_in.get("predicate") or "states"),
                object_text=str(text or ""),
                confidence=spec["confidence"],
                ts=ts,
                source=source,
                meta=meta_in,
            )
        elif spec["kind"] == "summary":
            period = str(meta_in.get("mode") or meta_in.get("period") or "ad_hoc")
            self._upsert_summary(
                source_name="legacy_summary",
                source_key=source_key,
                period=period,
                started_ts=ts,
                ended_ts=ts,
                text=str(text or ""),
                source=source,
                meta=meta_in,
            )
        return out

    def _touch_memory_items(self, ids: List[str]) -> None:
        if not ids:
            return
        now = _now_ts()
        placeholders = ", ".join(["?"] * len(ids))
        with self._lock:
            self._conn.execute(
                f"""
                UPDATE memory_items
                SET last_access_ts = ?, access_count = access_count + 1
                WHERE id IN ({placeholders})
                """,
                (now, *ids),
            )

    def _search_memory_items(self, match: str, limit: int) -> List[Dict[str, Any]]:
        if self._has_fts and match:
            src = self._query(
                """
                SELECT
                    mi.id, mi.item_kind, mi.layer, mi.text, mi.salience, mi.confidence,
                    mi.created_ts, mi.source, mi.scope, mi.pin, mi.meta_json,
                    bm25(memory_items_fts) AS rank
                FROM memory_items_fts
                JOIN memory_items mi ON mi.rowid = memory_items_fts.rowid
                WHERE memory_items_fts MATCH ? AND mi.active = 1
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        else:
            src = self._query(
                """
                SELECT id, item_kind, layer, text, salience, confidence, created_ts,
                       source, scope, pin, meta_json, 100.0 AS rank
                FROM memory_items
                WHERE active = 1
                ORDER BY pin DESC, salience DESC, created_ts DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows: List[Dict[str, Any]] = []
        for row in src:
            boost = float(row["salience"] or 0.0) + (0.6 if int(row["pin"] or 0) else 0.0)
            rows.append(
                {
                    "id": row["id"],
                    "type": row["item_kind"],
                    "text": row["text"],
                    "ts": int(row["created_ts"] or 0),
                    "meta": {
                        **_json_loads(row["meta_json"]),
                        "layer": row["layer"],
                        "scope": row["scope"],
                        "source": row["source"],
                        "_source_table": "memory_items",
                    },
                    "_score": _calc_score(row["rank"], weight=2.2, boost=max(0.2, boost)),
                }
            )
        return rows

    def _search_identity(self, match: str, limit: int) -> List[Dict[str, Any]]:
        if self._has_fts and match:
            src = self._query(
                """
                SELECT ii.id, ii.label, ii.text, ii.priority, ii.source, ii.updated_ts, ii.meta_json, bm25(identity_items_fts) AS rank
                FROM identity_items_fts
                JOIN identity_items ii ON ii.rowid = identity_items_fts.rowid
                WHERE identity_items_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        else:
            src = self._query(
                """
                SELECT id, label, text, priority, source, updated_ts, meta_json, 100.0 AS rank
                FROM identity_items
                ORDER BY priority DESC, updated_ts DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows: List[Dict[str, Any]] = []
        for row in src:
            rows.append(
                {
                    "id": row["id"],
                    "type": "identity",
                    "text": row["text"],
                    "ts": int(row["updated_ts"] or 0),
                    "meta": {
                        **_json_loads(row["meta_json"]),
                        "label": row["label"],
                        "source": row["source"],
                        "_source_table": "identity_items",
                    },
                    "_score": _calc_score(row["rank"], weight=3.0, boost=max(0.5, float(row["priority"] or 1.0))),
                }
            )
        return rows

    def _search_facts(self, match: str, limit: int) -> List[Dict[str, Any]]:
        if self._has_fts and match:
            src = self._query(
                """
                SELECT f.id, f.fact_kind, f.subject, f.predicate, f.object_text, f.confidence, f.ts, f.source, f.meta_json, bm25(facts_fts) AS rank
                FROM facts_fts
                JOIN facts f ON f.rowid = facts_fts.rowid
                WHERE facts_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        else:
            src = self._query(
                """
                SELECT id, fact_kind, subject, predicate, object_text, confidence, ts, source, meta_json, 100.0 AS rank
                FROM facts
                ORDER BY confidence DESC, ts DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows: List[Dict[str, Any]] = []
        for row in src:
            rows.append(
                {
                    "id": row["id"],
                    "type": row["fact_kind"] or "fact",
                    "text": row["object_text"],
                    "ts": int(row["ts"] or 0),
                    "meta": {
                        **_json_loads(row["meta_json"]),
                        "subject": row["subject"],
                        "predicate": row["predicate"],
                        "source": row["source"],
                        "_source_table": "facts",
                    },
                    "_score": _calc_score(row["rank"], weight=1.9, boost=max(0.2, float(row["confidence"] or 0.0))),
                }
            )
        return rows

    def _search_episodes(self, match: str, limit: int) -> List[Dict[str, Any]]:
        if self._has_fts and match:
            src = self._query(
                """
                SELECT e.id, e.text, e.summary, e.importance, e.ended_ts, e.source, e.meta_json, bm25(episodes_fts) AS rank
                FROM episodes_fts
                JOIN episodes e ON e.rowid = episodes_fts.rowid
                WHERE episodes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        else:
            src = self._query(
                """
                SELECT id, text, summary, importance, ended_ts, source, meta_json, 100.0 AS rank
                FROM episodes
                ORDER BY importance DESC, ended_ts DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows: List[Dict[str, Any]] = []
        for row in src:
            rows.append(
                {
                    "id": row["id"],
                    "type": "episode",
                    "text": row["summary"] or row["text"],
                    "ts": int(row["ended_ts"] or 0),
                    "meta": {
                        **_json_loads(row["meta_json"]),
                        "source": row["source"],
                        "_source_table": "episodes",
                    },
                    "_score": _calc_score(row["rank"], weight=1.5, boost=max(0.2, float(row["importance"] or 0.0))),
                }
            )
        return rows

    def _search_summaries(self, match: str, limit: int) -> List[Dict[str, Any]]:
        if self._has_fts and match:
            src = self._query(
                """
                SELECT s.id, s.period, s.text, s.source, s.ended_ts, s.meta_json, bm25(summaries_fts) AS rank
                FROM summaries_fts
                JOIN summaries s ON s.rowid = summaries_fts.rowid
                WHERE summaries_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        else:
            src = self._query(
                """
                SELECT id, period, text, source, ended_ts, meta_json, 100.0 AS rank
                FROM summaries
                ORDER BY ended_ts DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows: List[Dict[str, Any]] = []
        for row in src:
            rows.append(
                {
                    "id": row["id"],
                    "type": "summary",
                    "text": row["text"],
                    "ts": int(row["ended_ts"] or 0),
                    "meta": {
                        **_json_loads(row["meta_json"]),
                        "period": row["period"],
                        "source": row["source"],
                        "_source_table": "summaries",
                    },
                    "_score": _calc_score(row["rank"], weight=1.7, boost=1.0),
                }
            )
        return rows

    def _search_events(self, match: str, limit: int) -> List[Dict[str, Any]]:
        if self._has_fts and match:
            src = self._query(
                """
                SELECT e.id, e.event_kind, e.text, e.ts, e.source, e.scope, e.meta_json, bm25(events_fts) AS rank
                FROM events_fts
                JOIN events e ON e.rowid = events_fts.rowid
                WHERE events_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match, limit),
            )
        else:
            src = self._query(
                """
                SELECT id, event_kind, text, ts, source, scope, meta_json, 100.0 AS rank
                FROM events
                ORDER BY ts DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows: List[Dict[str, Any]] = []
        for row in src:
            rows.append(
                {
                    "id": row["id"],
                    "type": row["event_kind"] or "event",
                    "text": row["text"],
                    "ts": int(row["ts"] or 0),
                    "meta": {
                        **_json_loads(row["meta_json"]),
                        "scope": row["scope"],
                        "source": row["source"],
                        "_source_table": "events",
                    },
                    "_score": _calc_score(row["rank"], weight=0.9, boost=1.0),
                }
            )
        return rows

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        lim = max(1, min(50, int(limit or 8)))
        match = _match_query(query)
        merged: List[Dict[str, Any]] = []
        seen = set()
        memory_ids: List[str] = []
        for bucket in (
            self._search_identity(match, lim),
            self._search_facts(match, lim),
            self._search_memory_items(match, lim),
            self._search_episodes(match, lim),
            self._search_summaries(match, lim),
            self._search_events(match, lim),
        ):
            for row in bucket:
                key = (
                    str(row.get("type") or ""),
                    str(row.get("text") or "").strip().lower(),
                    int(row.get("ts") or 0) // 5,
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(row)
        merged.sort(key=lambda item: (float(item.get("_score") or 0.0), int(item.get("ts") or 0)), reverse=True)
        out = merged[:lim]
        for row in out:
            if str(((row.get("meta") or {}).get("_source_table") or "")) == "memory_items":
                memory_ids.append(str(row.get("id") or ""))
        self._touch_memory_items([rid for rid in memory_ids if rid])
        return out

    def shadow_compare(self, query: str, legacy: List[Dict[str, Any]], core_rows: List[Dict[str, Any]]) -> None:
        rec = {
            "ts": _now_ts(),
            "query": _clip(query, 240),
            "legacy_count": len(legacy or []),
            "core_count": len(core_rows or []),
            "legacy_head": [_clip(str((x or {}).get("text") or ""), 120) for x in (legacy or [])[:3]],
            "core_head": [_clip(str((x or {}).get("text") or ""), 120) for x in (core_rows or [])[:3]],
        }
        try:
            with self.shadow_log_path.open("a", encoding="utf-8") as f:
                f.write(_json_dumps(rec) + "\n")
        except Exception:
            pass

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for name in ("events", "memory_items", "facts", "identity_items", "episodes", "summaries", "import_runs"):
            try:
                rows = self._query(f"SELECT COUNT(*) AS n FROM {name}")
                out[name] = int(rows[0]["n"]) if rows else 0
            except Exception:
                out[name] = -1
        return out

    def status(self) -> Dict[str, Any]:
        imports = self._query(
            """
            SELECT source_name, source_path, started_ts, finished_ts, status, stats_json
            FROM import_runs
            ORDER BY finished_ts DESC
            LIMIT 10
            """
        )
        return {
            "ok": True,
            "path": str(self.path),
            "fts": bool(self._has_fts),
            "counts": self.counts(),
            "imports": [
                {
                    "source_name": row["source_name"],
                    "source_path": row["source_path"],
                    "started_ts": int(row["started_ts"] or 0),
                    "finished_ts": int(row["finished_ts"] or 0),
                    "status": row["status"],
                    "stats": _json_loads(row["stats_json"]),
                }
                for row in imports
            ],
        }

    def _record_import_run(self, source_name: str, source_path: str, started_ts: int, status: str, stats: Dict[str, Any]) -> None:
        finished_ts = _now_ts()
        run_id = f"imp_{uuid.uuid4().hex}"
        self._execute(
            """
            INSERT INTO import_runs(id, source_name, source_path, started_ts, finished_ts, status, stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, source_name, source_path, started_ts, finished_ts, status, _json_dumps(stats)),
        )

    def import_snapshot(self, path: Path) -> Dict[str, Any]:
        started = _now_ts()
        report: Dict[str, Any] = {"ok": True, "path": str(path), "events": 0, "memory_items": 0, "facts": 0, "summaries": 0}
        if not path.exists():
            report["ok"] = False
            report["error"] = "missing"
            self._record_import_run("snapshot", str(path), started, "missing", report)
            return report
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("snapshot must be a dict")
            for key, value in raw.items():
                if not isinstance(value, dict):
                    continue
                legacy_id = str(value.get("id") or key or uuid.uuid4().hex)
                text = str(value.get("text") or "")
                if not text:
                    continue
                kind = _normalize_kind(str(value.get("type") or "fact"))
                meta = dict(value.get("meta") or {})
                ts = _coerce_ts(value.get("ts"))
                if "vec" in value and isinstance(value.get("vec"), list):
                    meta.setdefault("legacy_vec_dim", len(value.get("vec") or []))
                event_id = self._upsert_event(
                    source_name="legacy_store",
                    source_key=legacy_id,
                    ts=ts,
                    event_kind=kind,
                    role=str(meta.get("role") or ""),
                    text=text,
                    source=str(meta.get("source") or "memory.json"),
                    scope=str(meta.get("scope") or "global"),
                    legacy_id=legacy_id,
                    source_ref=str(path),
                    meta=meta,
                )
                report["events"] += 1
                spec = self._classify_item(kind, text, meta, value)
                if not spec["promote"]:
                    continue
                mid = self._upsert_memory_item(
                    source_name="legacy_store",
                    source_key=legacy_id,
                    event_id=event_id,
                    item_kind=spec["kind"],
                    layer=spec["layer"],
                    text=text,
                    salience=spec["salience"],
                    confidence=spec["confidence"],
                    scope=spec["scope"],
                    source=str(meta.get("source") or "memory.json"),
                    created_ts=ts,
                    pin=spec["pin"],
                    legacy_id=legacy_id,
                    meta=meta,
                )
                report["memory_items"] += 1
                if spec["kind"] in {"fact", "goal", "doc", "doc_summary"}:
                    self._upsert_fact(
                        source_name="legacy_fact",
                        source_key=legacy_id,
                        memory_item_id=mid,
                        fact_kind=spec["kind"],
                        subject=str(meta.get("subject") or "memory"),
                        predicate=str(meta.get("predicate") or "states"),
                        object_text=text,
                        confidence=spec["confidence"],
                        ts=ts,
                        source=str(meta.get("source") or "memory.json"),
                        meta=meta,
                    )
                    report["facts"] += 1
                if spec["kind"] == "summary":
                    self._upsert_summary(
                        source_name="legacy_summary",
                        source_key=legacy_id,
                        period=str(meta.get("mode") or meta.get("period") or "ad_hoc"),
                        started_ts=ts,
                        ended_ts=ts,
                        text=text,
                        source=str(meta.get("source") or "memory.json"),
                        meta=meta,
                    )
                    report["summaries"] += 1
            self._record_import_run("snapshot", str(path), started, "ok", report)
            return report
        except Exception as exc:
            report["ok"] = False
            report["error"] = str(exc)
            self._record_import_run("snapshot", str(path), started, "error", report)
            return report

    def import_clean_memory(self, path: Path) -> Dict[str, Any]:
        started = _now_ts()
        report: Dict[str, Any] = {"ok": True, "path": str(path), "events": 0, "episodes": 0}
        if not path.exists():
            report["ok"] = False
            report["error"] = "missing"
            self._record_import_run("clean_memory", str(path), started, "missing", report)
            return report
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f):
                    raw_line = line.strip()
                    if not raw_line:
                        continue
                    try:
                        obj = json.loads(raw_line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    ts = _coerce_ts(obj.get("ts"))
                    user_text = str(obj.get("user") or "").strip()
                    assistant_text = str(obj.get("assistant") or "").strip()
                    if not user_text and not assistant_text:
                        continue
                    base_key = _stable_key("clean_memory", idx, ts, user_text, assistant_text)
                    if user_text:
                        self._upsert_event(
                            source_name="clean_memory_user",
                            source_key=base_key,
                            ts=ts,
                            event_kind="dialog_user",
                            role="user",
                            text=user_text,
                            source="clean_memory.jsonl",
                            scope="dialog",
                            legacy_id="",
                            source_ref=str(path),
                            meta={"pair": "user", "line_index": idx},
                        )
                        report["events"] += 1
                    if assistant_text:
                        self._upsert_event(
                            source_name="clean_memory_assistant",
                            source_key=base_key,
                            ts=ts,
                            event_kind="dialog_assistant",
                            role="assistant",
                            text=assistant_text,
                            source="clean_memory.jsonl",
                            scope="dialog",
                            legacy_id="",
                            source_ref=str(path),
                            meta={"pair": "assistant", "line_index": idx},
                        )
                        report["events"] += 1
                    episode_text = "\n".join(
                        part
                        for part in (
                            f"USER: {user_text}" if user_text else "",
                            f"ASSISTANT: {assistant_text}" if assistant_text else "",
                        )
                        if part
                    )
                    self._upsert_episode(
                        source_name="clean_memory_episode",
                        source_key=base_key,
                        started_ts=ts,
                        ended_ts=ts,
                        importance=0.75,
                        text=episode_text,
                        summary=_clip(assistant_text or user_text, 320),
                        source="clean_memory.jsonl",
                        source_ref=str(path),
                        meta={"line_index": idx},
                    )
                    report["episodes"] += 1
            self._record_import_run("clean_memory", str(path), started, "ok", report)
            return report
        except Exception as exc:
            report["ok"] = False
            report["error"] = str(exc)
            self._record_import_run("clean_memory", str(path), started, "error", report)
            return report

    def import_journal(self, path: Path) -> Dict[str, Any]:
        started = _now_ts()
        report: Dict[str, Any] = {"ok": True, "path": str(path), "events": 0}
        if not path.exists():
            report["ok"] = False
            report["error"] = "missing"
            self._record_import_run("journal", str(path), started, "missing", report)
            return report
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f):
                    raw_line = line.strip()
                    if not raw_line:
                        continue
                    try:
                        obj = json.loads(raw_line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    ts = _coerce_ts(obj.get("ts"))
                    kind = _normalize_kind(str(obj.get("kind") or "event"))
                    source = str(obj.get("source") or "journal")
                    payload = obj.get("payload")
                    payload_meta = payload if isinstance(payload, dict) else {"payload": payload}
                    payload_text = str(payload_meta.get("text") or "")
                    if not payload_text:
                        payload_text = f"{kind}: {_clip(_json_dumps(payload_meta), 240)}"
                    event_key = _stable_key("journal", idx, ts, kind, payload_text, source)
                    self._upsert_event(
                        source_name="journal_events",
                        source_key=event_key,
                        ts=ts,
                        event_kind=kind,
                        role="system",
                        text=payload_text,
                        source=source,
                        scope="journal",
                        legacy_id="",
                        source_ref=str(path),
                        meta={
                            "ok": _parse_bool(obj.get("ok")),
                            "error": str(obj.get("error") or ""),
                            "trace_id": str(obj.get("trace_id") or ""),
                            **payload_meta,
                        },
                    )
                    report["events"] += 1
            self._record_import_run("journal", str(path), started, "ok", report)
            return report
        except Exception as exc:
            report["ok"] = False
            report["error"] = str(exc)
            self._record_import_run("journal", str(path), started, "error", report)
            return report

    def import_identity(self, anchor_path: Path, core_facts_path: Path, identity_dynamic_path: Path) -> Dict[str, Any]:
        started = _now_ts()
        report: Dict[str, Any] = {
            "ok": True,
            "anchor_path": str(anchor_path),
            "core_facts_path": str(core_facts_path),
            "identity_dynamic_path": str(identity_dynamic_path),
            "identity_items": 0,
            "facts": 0,
        }
        try:
            now = _now_ts()
            if anchor_path.exists():
                anchor_text = anchor_path.read_text(encoding="utf-8", errors="replace").strip()
                if anchor_text:
                    self._upsert_identity_item(
                        source_name="identity_anchor",
                        source_key="anchor",
                        label="anchor",
                        text=anchor_text,
                        priority=1.0,
                        source="anchor.txt",
                        created_ts=now,
                        meta={"path": str(anchor_path)},
                    )
                    report["identity_items"] += 1
            if core_facts_path.exists():
                for idx, line in enumerate(core_facts_path.read_text(encoding="utf-8", errors="replace").splitlines()):
                    fact_text = line.strip()
                    if not fact_text:
                        continue
                    key = _stable_key("core_fact", idx, fact_text)
                    self._upsert_identity_item(
                        source_name="identity_core_fact",
                        source_key=key,
                        label="core_fact",
                        text=fact_text,
                        priority=0.95,
                        source="core_facts.txt",
                        created_ts=now,
                        meta={"path": str(core_facts_path), "line_index": idx},
                    )
                    self._upsert_fact(
                        source_name="identity_core_fact",
                        source_key=key,
                        memory_item_id=None,
                        fact_kind="identity",
                        subject="self",
                        predicate="core_fact",
                        object_text=fact_text,
                        confidence=0.98,
                        ts=now,
                        source="core_facts.txt",
                        meta={"path": str(core_facts_path), "line_index": idx},
                    )
                    report["identity_items"] += 1
                    report["facts"] += 1
            if identity_dynamic_path.exists():
                obj = _json_loads(identity_dynamic_path.read_text(encoding="utf-8", errors="replace"))
                if obj:
                    voice = _clip(str(((obj.get("tone_profile") or {}).get("voice") or "")).strip(), 320)
                    if voice:
                        self._upsert_identity_item(
                            source_name="identity_dynamic",
                            source_key="tone_profile.voice",
                            label="tone_profile.voice",
                            text=voice,
                            priority=0.9,
                            source="identity_dynamic.json",
                            created_ts=now,
                            meta={"path": str(identity_dynamic_path)},
                        )
                        report["identity_items"] += 1
                    reflection = _clip(str(obj.get("self_reflection") or "").strip(), 320)
                    if reflection:
                        self._upsert_identity_item(
                            source_name="identity_dynamic",
                            source_key="self_reflection",
                            label="self_reflection",
                            text=reflection,
                            priority=0.92,
                            source="identity_dynamic.json",
                            created_ts=now,
                            meta={"path": str(identity_dynamic_path)},
                        )
                        report["identity_items"] += 1
                    lessons = obj.get("recent_lessons") or []
                    if isinstance(lessons, list):
                        for idx, lesson in enumerate(lessons[:12]):
                            txt = _clip(str(lesson or "").strip(), 320)
                            if not txt:
                                continue
                            self._upsert_identity_item(
                                source_name="identity_dynamic",
                                source_key=f"recent_lessons.{idx}",
                                label="recent_lesson",
                                text=txt,
                                priority=0.7,
                                source="identity_dynamic.json",
                                created_ts=now,
                                meta={"path": str(identity_dynamic_path), "index": idx},
                            )
                            report["identity_items"] += 1
            self._record_import_run("identity", str(identity_dynamic_path), started, "ok", report)
            return report
        except Exception as exc:
            report["ok"] = False
            report["error"] = str(exc)
            self._record_import_run("identity", str(identity_dynamic_path), started, "error", report)
            return report

    def import_all(
        self,
        *,
        snapshot: Optional[Path] = None,
        clean_memory: Optional[Path] = None,
        journal: Optional[Path] = None,
        anchor: Optional[Path] = None,
        core_facts: Optional[Path] = None,
        identity_dynamic: Optional[Path] = None,
    ) -> Dict[str, Any]:
        paths = _default_import_paths()
        report = {
            "ok": True,
            "db": str(self.path),
            "steps": {
                "snapshot": self.import_snapshot(snapshot or paths["snapshot"]),
                "clean_memory": self.import_clean_memory(clean_memory or paths["clean_memory"]),
                "journal": self.import_journal(journal or paths["journal"]),
                "identity": self.import_identity(
                    anchor or paths["anchor"],
                    core_facts or paths["core_facts"],
                    identity_dynamic or paths["identity_dynamic"],
                ),
            },
            "status": self.status(),
        }
        report["ok"] = all(
            bool((step or {}).get("ok")) or str((step or {}).get("error") or "") == "missing"
            for step in report["steps"].values()
        )
        return report


def get_core(path: Optional[str] = None) -> MemoryCore:
    global _CORE_SINGLETON
    with _CORE_LOCK:
        target = str(_resolve_path(path or "", "data/memory_core/ester_memory.sqlite"))
        if _CORE_SINGLETON is None or str(_CORE_SINGLETON.path) != target:
            if _CORE_SINGLETON is not None:
                _CORE_SINGLETON.close()
            _CORE_SINGLETON = MemoryCore(path=target)
        return _CORE_SINGLETON


def reset_core_for_tests() -> None:
    global _CORE_SINGLETON
    with _CORE_LOCK:
        if _CORE_SINGLETON is not None:
            _CORE_SINGLETON.close()
        _CORE_SINGLETON = None


def write_memory_add(kind: str, text: str, meta: Optional[Dict[str, Any]] = None, legacy_record: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return get_core().write_memory_add(kind, text, meta=meta, legacy_record=legacy_record)


def search_legacy(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    return get_core().search(query, limit=limit)


def shadow_compare(query: str, legacy: List[Dict[str, Any]], core_rows: List[Dict[str, Any]]) -> None:
    get_core().shadow_compare(query, legacy, core_rows)


def import_all() -> Dict[str, Any]:
    return get_core().import_all()


def status() -> Dict[str, Any]:
    return get_core().status()


def default_import_paths() -> Dict[str, str]:
    return {k: str(v) for k, v in _default_import_paths().items()}


__all__ = [
    "MemoryCore",
    "core_enabled",
    "default_import_paths",
    "dual_write_enabled",
    "get_core",
    "import_all",
    "read_cutover_enabled",
    "reset_core_for_tests",
    "search_legacy",
    "shadow_compare",
    "shadow_read_enabled",
    "status",
    "write_memory_add",
]
