# -*- coding: utf-8 -*-
"""
cron/snapshot.py — nochnye snapshoty indeksov (lokalno, bez vneshnikh zavisimostey).

Zapusk:
  • Razovo:         python -m cron.snapshot --once
  • Po raspisaniyu:  SNAPSHOT_CRON=02:30 python -m cron.snapshot
  • Parametry:      SNAPSHOT_DIR=./data/snapshots, INDEX_ROOT=./data/index/faiss, SNAPSHOT_KEEP=14

Chto delaet:
  • Sobiraet katalogi shardov iz INDEX_ROOT i upakovyvaet tar.{zst|gz} v SNAPSHOT_DIR.
  • Esli dostupen zstandard — .zst, inache — .gz.
  • (Opts.) uderzhivaet ne bolee SNAPSHOT_KEEP poslednikh snapshotov.

Zemnoy abzats (inzheneriya)
Eto «nochnaya fotokamera stanka»: delaet akkuratnyy snimok sostoyaniya indeksov,
chtoby posle vnezapnogo otklyucheniya pitaniya mozhno bylo bystro vosstanovitsya.

Mosty
- Yavnyy (Arkhitektura ↔ Nadezhnost): regulyarnye snapshoty — strakhovka pri sboyakh/oshibkakh operatora.
- Skrytyy 1 (Kibernetika ↔ Operatsii): vneshniy medlennyy kontur (planirovschik) stabiliziruet sistemu posle pikov.
- Skrytyy 2 (Anatomiya ↔ PO): kak son — konsolidatsiya «pamyati» v dolgovremennoe khranilische.

# c=a+b
"""
from __future__ import annotations

import argparse
import os
import tarfile
import time
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _env(name: str, default: str) -> str:
    return os.getenv(name) or default

def _index_root() -> str:
    return _env("INDEX_ROOT", os.path.join(_env("PERSIST_DIR", _env("DATA_DIR","./data")), "index", "faiss"))

def _snapshot_dir() -> str:
    return _env("SNAPSHOT_DIR", os.path.join(_env("PERSIST_DIR", _env("DATA_DIR","./data")), "snapshots"))

def _list_shards(root: str) -> List[str]:
    try:
        return [n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))]
    except Exception:
        return []

def _compress_tar(tar_path: str) -> str:
    zst_path = tar_path + ".zst"
    try:
        import zstandard as zstd  # type: ignore
        cctx = zstd.ZstdCompressor(level=10)
        with open(tar_path, "rb") as src, open(zst_path, "wb") as dst:
            dst.write(cctx.compress(src.read()))
        os.remove(tar_path)
        return zst_path
    except Exception:
        import gzip
        gz_path = tar_path + ".gz"
        with open(tar_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
            dst.write(src.read())
        os.remove(tar_path)
        return gz_path

def _snapshot_once(shard: str | None = None) -> str:
    root = _index_root()
    snapdir = _snapshot_dir()
    os.makedirs(snapdir, exist_ok=True)
    shards = [shard] if shard else _list_shards(root)
    if not shards:
        raise SystemExit("no shards to snapshot")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    tar_path = os.path.join(snapdir, f"index__{shard or 'all'}__{stamp}.tar")
    with tarfile.open(tar_path, mode="w") as tar:
        for s in shards:
            p = os.path.join(root, s)
            if os.path.isdir(p):
                tar.add(p, arcname=s)
    final = _compress_tar(tar_path)
    return final

def _trim_keep() -> int:
    keep = int(_env("SNAPSHOT_KEEP", "0") or "0")
    if keep <= 0:
        return 0
    sd = _snapshot_dir()
    try:
        files = sorted(
            [os.path.join(sd, f) for f in os.listdir(sd) if f.startswith("index__")],
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )
        for f in files[keep:]:
            try:
                os.remove(f)
            except Exception:
                pass
        return max(0, len(files) - keep)
    except Exception:
        return 0

def _seconds_until(hhmm: str) -> int:
    try:
        hh, mm = [int(x) for x in hhmm.strip().split(":")]
    except Exception:
        hh, mm = 2, 30  # defolt 02:30
    now = time.localtime()
    target = time.struct_time((now.tm_year, now.tm_mon, now.tm_mday, hh, mm, 0,
                               now.tm_wday, now.tm_yday, now.tm_isdst))
    now_s = time.mktime(now)
    tgt_s = time.mktime(target)
    if tgt_s <= now_s:
        tgt_s += 86400
    return int(tgt_s - now_s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="sdelat odin snapshot i vyyti")
    ap.add_argument("--shard", default=None, help="ogranichit odnim shardom")
    args = ap.parse_args()

    if args.once:
        path = _snapshot_once(shard=args.shard)
        removed = _trim_keep()
        print(f"OK snapshot: {path} (trimmed {removed})")
        return

    cron = _env("SNAPSHOT_CRON", "02:30")
    while True:
        wait = _seconds_until(cron)
        print(f"[snapshot] next at {cron}, sleep {wait}s")
        time.sleep(max(1, wait))
        try:
            path = _snapshot_once(shard=args.shard)
            removed = _trim_keep()
            print(f"[snapshot] OK: {path} (trimmed {removed})")
        except SystemExit as e:
            print(f"[snapshot] skip: {e}")
        except Exception as e:
            print(f"[snapshot] error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()