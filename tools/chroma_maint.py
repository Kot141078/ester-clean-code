# -*- coding: utf-8 -*-
"""
tools/chroma_maint.py — obsluzhivanie Chroma SQLite (checkpoint/optimize/vacuum/backup).

Zachem:
- U tebya chroma.sqlite3 ~6+ GB. Lyubaya operatsiya, kotoraya trogaet Chroma (RAG ingest/query, cleanup),
  mozhet "podvisat" iz-za WAL/fragmentatsii/rosta freelist.
- VACUUM i WAL checkpoint chasto vozvraschayut skorost i umenshayut razmer.

VAZhNO (L4):
- Ostanovi Ester/protsess Chroma pered obsluzhivaniem (inache budet lock).
- Ubedis, chto na diske est svobodnoe mesto: VACUUM mozhet vremenno trebovat ~razmer BD.

MOSTY:
- Yavnyy: (Audit → Control) — izmeryaem sostoyanie BD (page_count/freelist) i korrektiruem (vacuum).
- Skrytyy #1: (Kibernetika Ashby → ustoychivost) — obsluzhivaem kontur khraneniya, umenshaya dreyf/iznos.
- Skrytyy #2: (Infoteoriya → propusknaya sposobnost) — menshe “pustykh stranits” = vyshe poleznaya emkost.
ZEMNOY ABZATs:
Eto kak servis korobki peredach: maslo ne dobavlyaet moschnosti, no ubiraet ryvki i prodlevaet resurs.

c=a+b
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class DbStats:
    journal_mode: str = ""
    page_size: int = 0
    page_count: int = 0
    freelist_count: int = 0


def _fmt_bytes(n: int) -> str:
    if n < 0:
        return str(n)
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024.0 or u == units[-1]:
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{n} B"


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def _print_file_sizes(db_path: str) -> None:
    wal = db_path + "-wal"
    shm = db_path + "-shm"
    print("Files:")
    print(f"  db : {_fmt_bytes(_file_size(db_path))}  {db_path}")
    if os.path.exists(wal):
        print(f"  wal: {_fmt_bytes(_file_size(wal))}  {wal}")
    if os.path.exists(shm):
        print(f"  shm: {_fmt_bytes(_file_size(shm))}  {shm}")


def _connect(db_path: str, timeout: float = 30.0) -> sqlite3.Connection:
    # isolation_level=None -> autocommit (udobno dlya PRAGMA i VACUUM)
    con = sqlite3.connect(db_path, timeout=timeout, isolation_level=None)
    return con


def _pragma_str(con: sqlite3.Connection, name: str) -> str:
    cur = con.execute(f"PRAGMA {name};")
    row = cur.fetchone()
    return str(row[0]) if row and row[0] is not None else ""


def _pragma_int(con: sqlite3.Connection, name: str) -> int:
    cur = con.execute(f"PRAGMA {name};")
    row = cur.fetchone()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def get_stats(con: sqlite3.Connection) -> DbStats:
    return DbStats(
        journal_mode=_pragma_str(con, "journal_mode"),
        page_size=_pragma_int(con, "page_size"),
        page_count=_pragma_int(con, "page_count"),
        freelist_count=_pragma_int(con, "freelist_count"),
    )


def wal_checkpoint(con: sqlite3.Connection, mode: str = "TRUNCATE") -> Tuple[int, int, int]:
    """
    Returns (busy, log, checkpointed)
    """
    cur = con.execute(f"PRAGMA wal_checkpoint({mode});")
    row = cur.fetchone()
    if not row:
        return (0, 0, 0)
    return (int(row[0]), int(row[1]), int(row[2]))


def optimize(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA optimize;")


def vacuum(con: sqlite3.Connection) -> None:
    con.execute("VACUUM;")


def backup_file(db_path: str, out_path: Optional[str] = None) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    if not out_path:
        out_path = db_path + f".bak_{ts}"
    shutil.copy2(db_path, out_path)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to chroma.sqlite3")
    ap.add_argument("--timeout", type=float, default=30.0, help="sqlite busy timeout (sec)")
    ap.add_argument("--backup", action="store_true", help="Create backup copy before changes")
    ap.add_argument("--backup-path", default="", help="Optional backup file path")
    ap.add_argument("--checkpoint", action="store_true", help="Run WAL checkpoint(TRUNCATE)")
    ap.add_argument("--optimize", action="store_true", help="Run PRAGMA optimize")
    ap.add_argument("--vacuum", action="store_true", help="Run VACUUM (can be slow)")
    args = ap.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"[ERR] DB not found: {db_path}")
        return 2

    print("=" * 72)
    _print_file_sizes(db_path)

    if args.backup:
        bp = args.backup_path.strip() or None
        out = backup_file(db_path, bp)
        print(f"[OK] Backup created: {out} ({_fmt_bytes(_file_size(out))})")

    print("=" * 72)
    con = _connect(db_path, timeout=args.timeout)
    try:
        st0 = get_stats(con)
        print("Before:")
        print(f"  journal_mode   : {st0.journal_mode}")
        print(f"  page_size      : {st0.page_size}")
        print(f"  page_count     : {st0.page_count}")
        print(f"  freelist_count : {st0.freelist_count}  (~free={_fmt_bytes(st0.freelist_count * st0.page_size)})")

        if args.checkpoint:
            busy, log, ckpt = wal_checkpoint(con, "TRUNCATE")
            print(f"[OK] wal_checkpoint(TRUNCATE): busy={busy} log={log} checkpointed={ckpt}")
            _print_file_sizes(db_path)

        if args.optimize:
            t0 = time.time()
            optimize(con)
            print(f"[OK] PRAGMA optimize; took {time.time() - t0:.2f}s")

        if args.vacuum:
            t0 = time.time()
            print("[..] VACUUM started (mozhet zanyat dolgo na bolshikh BD)...")
            vacuum(con)
            print(f"[OK] VACUUM done; took {time.time() - t0:.2f}s")
            _print_file_sizes(db_path)

        st1 = get_stats(con)
        print("After:")
        print(f"  journal_mode   : {st1.journal_mode}")
        print(f"  page_size      : {st1.page_size}")
        print(f"  page_count     : {st1.page_count}")
        print(f"  freelist_count : {st1.freelist_count}  (~free={_fmt_bytes(st1.freelist_count * st1.page_size)})")

    finally:
        try:
            con.close()
        except Exception:
            pass

    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())