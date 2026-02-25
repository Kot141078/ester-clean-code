# -*- coding: utf-8 -*-
"""SQLite-backed outbox with backward-compatible helpers."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


Row = Tuple[int, float, str, str, str, str, int, str]

DDL = """
CREATE TABLE IF NOT EXISTS outgoing (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  channel TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  text TEXT NOT NULL,
  status TEXT NOT NULL,
  http_status INTEGER NOT NULL,
  request_id TEXT NOT NULL,
  raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outgoing_ts ON outgoing(ts DESC);
CREATE INDEX IF NOT EXISTS idx_outgoing_status ON outgoing(status);
"""

_MEM_CONN_CACHE: dict[str, sqlite3.Connection] = {}


def _db_path() -> str:
    return os.getenv("MESSAGING_DB_PATH", "data/messaging.db")


def _memory_conn(cache_key: str) -> sqlite3.Connection:
    conn = _MEM_CONN_CACHE.get(cache_key)
    if conn is None:
        conn = sqlite3.connect(":memory:", timeout=5.0, isolation_level=None, check_same_thread=False)
        conn.executescript(DDL)
        _MEM_CONN_CACHE[cache_key] = conn
    return conn


def _conn() -> sqlite3.Connection:
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def _open(prefer_wal: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL" if prefer_wal else "PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    conn = _open(prefer_wal=True)
    try:
        conn.executescript(DDL)
        return conn
    except sqlite3.OperationalError as e:
        conn.close()
        msg = str(e).lower()
        if "disk i/o" not in msg and "malformed" not in msg:
            raise
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
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
            return _memory_conn(path)


def _insert_row(
    channel: str,
    chat_id: str,
    text: str,
    status: str,
    http_status: int,
    request_id: str,
    raw: Any,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO outgoing(ts,channel,chat_id,text,status,http_status,request_id,raw_json)
            VALUES(?,?,?,?,?,?,?,?)""",
            (
                float(time.time()),
                str(channel or "unknown"),
                str(chat_id or ""),
                str(text or ""),
                str(status or "new"),
                int(http_status or 0),
                str(request_id or ""),
                json.dumps(raw if raw is not None else {}, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def _parse_target(target: str) -> Tuple[str, str]:
    raw = str(target or "")
    if ":" in raw:
        channel, chat_id = raw.split(":", 1)
        return channel.strip().lower(), chat_id.strip()
    return "unknown", raw


def add_outgoing(*args, **kwargs):
    """
    Supported signatures:
      add_outgoing({"to":"telegram:42","text":"hi","status":"new"})
      add_outgoing(channel, chat_id, text, status, http_status, request_id)
    """
    if args and isinstance(args[0], dict):
        msg = dict(args[0] or {})
        channel = str(msg.get("channel") or msg.get("kind") or "").strip().lower()
        chat_id = str(msg.get("chat_id") or "")
        target = str(msg.get("to") or "")
        if target and not chat_id:
            ch2, id2 = _parse_target(target)
            if not channel:
                channel = ch2
            chat_id = id2
        row_id = _insert_row(
            channel or "unknown",
            chat_id,
            str(msg.get("text") or ""),
            str(msg.get("status") or "new"),
            int(msg.get("http_status") or 0),
            str(msg.get("request_id") or msg.get("id") or ""),
            msg,
        )
        return {"ok": True, "id": row_id}

    if len(args) >= 6:
        channel, chat_id, text, status, http_status, request_id = args[:6]
        return _insert_row(
            str(channel or ""),
            str(chat_id or ""),
            str(text or ""),
            str(status or "new"),
            int(http_status or 0),
            str(request_id or ""),
            {"source": "legacy_add_outgoing"},
        )

    # kwargs fallback for explicit named arguments
    return _insert_row(
        str(kwargs.get("channel") or ""),
        str(kwargs.get("chat_id") or ""),
        str(kwargs.get("text") or ""),
        str(kwargs.get("status") or "new"),
        int(kwargs.get("http_status") or 0),
        str(kwargs.get("request_id") or ""),
        kwargs,
    )


def list_outgoing(limit: int = 100, offset: int = 0, status: Optional[str] = None) -> List[Row]:
    lim = max(1, int(limit))
    off = max(0, int(offset))
    if status:
        sql = """
            SELECT id,ts,channel,chat_id,text,status,http_status,request_id
            FROM outgoing WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?
        """
        args: Iterable[Any] = (str(status), lim, off)
    else:
        sql = """
            SELECT id,ts,channel,chat_id,text,status,http_status,request_id
            FROM outgoing ORDER BY id DESC LIMIT ? OFFSET ?
        """
        args = (lim, off)
    with _conn() as conn:
        rows = conn.execute(sql, tuple(args)).fetchall()
    return [
        (
            int(r[0]),
            float(r[1]),
            str(r[2]),
            str(r[3]),
            str(r[4]),
            str(r[5]),
            int(r[6] or 0),
            str(r[7] or ""),
        )
        for r in rows
    ]


def list_outgoing_paged(
    *,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    page: Optional[int] = None,
    size: Optional[int] = None,
):
    # Old API compatibility: page+size returns a dict payload.
    if page is not None or size is not None:
        p = max(1, int(page or 1))
        s = max(1, int(size or limit))
        rows = list_outgoing(limit=s, offset=(p - 1) * s, status=status)
        with _conn() as conn:
            if status:
                total = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM outgoing WHERE status=?", (str(status),)
                    ).fetchone()[0]
                )
            else:
                total = int(conn.execute("SELECT COUNT(*) FROM outgoing").fetchone()[0])
        items = [
            {
                "id": row[0],
                "ts": row[1],
                "channel": row[2],
                "chat_id": row[3],
                "text": row[4],
                "status": row[5],
                "http_status": row[6],
                "request_id": row[7],
            }
            for row in rows
        ]
        return {"ok": True, "page": p, "size": s, "total": total, "items": items}
    return list_outgoing(limit=limit, offset=offset, status=status)


def clear_outgoing() -> Dict[str, Any]:
    with _conn() as conn:
        conn.execute("DELETE FROM outgoing")
    return {"ok": True}


def record_attempt(*args, **kwargs) -> Dict[str, Any]:
    """
    Supported signatures:
      record_attempt(message_id, ok, info_dict)
      record_attempt(channel, chat_id, text, http_status, status, message_id, raw_json)
    """
    if len(args) >= 2 and isinstance(args[1], bool):
        message_id = int(args[0]) if str(args[0]).isdigit() else None
        ok = bool(args[1])
        info = args[2] if len(args) >= 3 else {}
        if message_id is not None:
            with _conn() as conn:
                conn.execute(
                    "UPDATE outgoing SET status=?, raw_json=? WHERE id=?",
                    (
                        "ok" if ok else "fail",
                        json.dumps(info or {}, ensure_ascii=False),
                        message_id,
                    ),
                )
        return {"ok": True}

    if len(args) >= 7:
        channel, chat_id, text, http_status, status, message_id, raw = args[:7]
        _insert_row(
            str(channel or ""),
            str(chat_id or ""),
            str(text or ""),
            str(status or "new"),
            int(http_status or 0),
            str(message_id or ""),
            raw,
        )
        return {"ok": True}

    _insert_row(
        str(kwargs.get("channel") or ""),
        str(kwargs.get("chat_id") or ""),
        str(kwargs.get("text") or ""),
        str(kwargs.get("status") or "new"),
        int(kwargs.get("http_status") or 0),
        str(kwargs.get("request_id") or ""),
        kwargs,
    )
    return {"ok": True}


def resend(message_id: int) -> Dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id,channel,chat_id,text,status,http_status,request_id,raw_json
            FROM outgoing WHERE id=?
            """,
            (int(message_id),),
        ).fetchone()
    if not row:
        return {"ok": False, "error": "not_found", "status": 404}

    channel = str(row[1] or "").lower()
    chat_id = str(row[2] or "")
    text = str(row[3] or "")
    result: Dict[str, Any]

    try:
        if channel == "telegram":
            from messaging.telegram_adapter import TelegramAdapter

            result = TelegramAdapter().send_message(chat_id, text)
        elif channel == "whatsapp":
            from messaging.whatsapp_adapter import WhatsAppAdapter

            result = WhatsAppAdapter().send_text(chat_id, text)
        else:
            result = {"ok": False, "status": 0, "body": "unsupported_channel"}
    except Exception as exc:
        result = {"ok": False, "status": 0, "body": str(exc)}

    status_code = int(result.get("status") or result.get("http_status") or 0)
    status = "resent:ok" if bool(result.get("ok")) else "resent:fail"
    new_id = _insert_row(
        channel,
        chat_id,
        text,
        status,
        status_code,
        f"resent:{message_id}",
        result,
    )
    return {"ok": bool(result.get("ok")), "status": status_code, "id": new_id}
