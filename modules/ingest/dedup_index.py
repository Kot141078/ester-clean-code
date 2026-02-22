# -*- coding: utf-8 -*-
"""
Durable dedup index for ingest artifacts (sqlite, stdlib-only).
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, Optional, Tuple

from modules.ingest.common import persist_dir


def _db_path() -> str:
    root = os.path.join(persist_dir(), "ingest")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "dedup.sqlite")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
          sha TEXT PRIMARY KEY,
          size INTEGER NOT NULL DEFAULT 0,
          first_path TEXT NOT NULL DEFAULT '',
          created_ts INTEGER NOT NULL DEFAULT 0,
          count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS links (
          sha TEXT NOT NULL,
          path TEXT NOT NULL,
          created_ts INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (sha, path)
        )
        """
    )
    con.commit()
    return con


def _looks_like_sha(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip().lower()
    if len(v) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in v)


def _parse_should_ingest_args(*args, **kwargs) -> Tuple[str, int]:
    sha = kwargs.get("sha")
    size = kwargs.get("size", 0)
    if args:
        if len(args) >= 2 and _looks_like_sha(args[1]):
            # new signature: should_ingest(path, sha, size=..., mtime=..., meta=...)
            sha = args[1]
            if len(args) >= 3:
                size = args[2]
        else:
            # legacy signature: should_ingest(sha, size=...)
            sha = args[0]
            if len(args) >= 2:
                size = args[1]
    if not _looks_like_sha(sha):
        raise ValueError("sha is required (hex sha256)")
    return str(sha), int(size or 0)


def _parse_record_ingest_args(*args, **kwargs) -> Tuple[str, str, int, Dict[str, Any]]:
    sha = kwargs.get("sha")
    path = kwargs.get("path")
    size = kwargs.get("size", 0)
    meta = dict(kwargs.get("meta") or {})

    if args:
        if len(args) == 1:
            # common hybrid call: record_ingest(sha, path=..., size=..., meta=...)
            if _looks_like_sha(args[0]):
                sha = args[0]
            elif not path:
                path = args[0]
        elif len(args) >= 2 and _looks_like_sha(args[0]):
            # legacy: record_ingest(sha, path, size, meta)
            sha = args[0]
            path = args[1]
            if len(args) >= 3:
                size = args[2]
            if len(args) >= 4 and isinstance(args[3], dict):
                meta = dict(args[3])
        elif len(args) >= 2 and _looks_like_sha(args[1]):
            # new: record_ingest(path, sha, size, meta)
            path = args[0]
            sha = args[1]
            if len(args) >= 3:
                size = args[2]
            if len(args) >= 4 and isinstance(args[3], dict):
                meta = dict(args[3])
        elif len(args) >= 2:
            # fallback to legacy order
            sha = args[0]
            path = args[1]
            if len(args) >= 3:
                size = args[2]
            if len(args) >= 4 and isinstance(args[3], dict):
                meta = dict(args[3])

    if not _looks_like_sha(sha):
        raise ValueError("sha is required (hex sha256)")
    return str(sha), str(path or ""), int(size or 0), meta


def _fetch_count_and_first_path(con: sqlite3.Connection, sha: str) -> Tuple[int, str]:
    row = con.execute("SELECT count, first_path FROM files WHERE sha=?", (sha,)).fetchone()
    if not row:
        return 0, ""
    return int(row[0] or 0), str(row[1] or "")


def should_ingest(*args, **kwargs) -> bool:
    sha, _size = _parse_should_ingest_args(*args, **kwargs)
    with _conn() as con:
        row = con.execute("SELECT 1 FROM files WHERE sha=? LIMIT 1", (sha,)).fetchone()
        return row is None


def record_ingest(*args, **kwargs) -> Dict[str, Any]:
    sha, path, size, meta = _parse_record_ingest_args(*args, **kwargs)
    ts = int(time.time())
    with _conn() as con:
        existing = con.execute("SELECT size, first_path, count FROM files WHERE sha=?", (sha,)).fetchone()
        if existing is None:
            con.execute(
                "INSERT INTO files(sha,size,first_path,created_ts,count) VALUES(?,?,?,?,?)",
                (sha, size, path, ts, 1),
            )
        else:
            con.execute("UPDATE files SET count=count+1 WHERE sha=?", (sha,))
        if path:
            con.execute(
                "INSERT OR IGNORE INTO links(sha,path,created_ts) VALUES(?,?,?)",
                (sha, path, ts),
            )
        con.commit()
        count, first_path = _fetch_count_and_first_path(con, sha)
    return {
        "ok": True,
        "sha": sha,
        "path": path,
        "size": size,
        "meta": meta,
        "count": count,
        "first_path": first_path,
    }


def link_duplicate(sha: str, path: str) -> Dict[str, Any]:
    if not _looks_like_sha(sha):
        raise ValueError("sha is required (hex sha256)")
    ts = int(time.time())
    with _conn() as con:
        row = con.execute("SELECT size, first_path FROM files WHERE sha=?", (sha,)).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO files(sha,size,first_path,created_ts,count) VALUES(?,?,?,?,?)",
                (sha, 0, str(path or ""), ts, 1),
            )
        else:
            con.execute("UPDATE files SET count=count+1 WHERE sha=?", (sha,))
        if path:
            con.execute(
                "INSERT OR IGNORE INTO links(sha,path,created_ts) VALUES(?,?,?)",
                (sha, str(path), ts),
            )
        con.commit()
        count, first_path = _fetch_count_and_first_path(con, sha)
        links = [
            str(r[0])
            for r in con.execute(
                "SELECT path FROM links WHERE sha=? ORDER BY created_ts ASC LIMIT 200",
                (sha,),
            ).fetchall()
        ]
    return {
        "ok": True,
        "sha": sha,
        "path": str(path or ""),
        "count": count,
        "first_path": first_path,
        "links": links,
    }
