# -*- coding: utf-8 -*-
"""modules/utils/ipc_lock.py

Cross-platform inter-process file lock + safe JSONL append.

Explicit bridge: c=a+b -> (a) chelovecheskiy "profile" + (b) protsedurnyy lock/fsync => (c) pamyat bez fantomov.
Hidden bridges:
- Ashby: "requisite variety" = vvodim rol writer/reader, chtoby sistema vyderzhivala bolshe rezhimov bez polomki.
- Cover&Thomas: zaschischaem kanal zapisi (journal) ot kolliziy -> menshe entropii/poter.
Earth (anatomiya/inzheneriya): kak klapan + sterilnoe pole - odin dostup, odna inektsiya za raz; inache sepsis dannykh.

No external deps. Works on Windows + Linux."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_IS_WINDOWS = (os.name == "nt")

if _IS_WINDOWS:
    import msvcrt  # type: ignore
else:
    import fcntl  # type: ignore


class LockError(RuntimeError):
    """Raised when an inter-process lock cannot be acquired within policy."""


@dataclass
class InterProcessFileLock:
    """
    OS-level exclusive lock on a lock file.

    - Windows: locks 1 byte via msvcrt.locking
    - Unix: fcntl.flock(LOCK_EX)

    Keep the handle open while locked.
    If the process dies, OS releases the lock.
    """
    path: str
    timeout_sec: float = 0.0  # 0 = non-blocking
    poll_interval_sec: float = 0.1

    _fh: Optional[object] = None
    _locked: bool = False

    def acquire(self) -> bool:
        if self._locked:
            return True

        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o666)
        fh = os.fdopen(fd, "r+", encoding="utf-8", errors="ignore", newline="")

        start = time.time()
        while True:
            try:
                if _IS_WINDOWS:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # best-effort debug info
                try:
                    fh.seek(0)
                    fh.truncate()
                    fh.write(json.dumps({
                        "pid": os.getpid(),
                        "ts": time.time(),
                        "role": "writer",
                    }, ensure_ascii=False))
                    fh.flush()
                except Exception:
                    pass

                self._fh = fh
                self._locked = True
                return True

            except Exception:
                if self.timeout_sec <= 0:
                    try:
                        fh.close()
                    except Exception:
                        pass
                    return False

                if (time.time() - start) >= self.timeout_sec:
                    try:
                        fh.close()
                    except Exception:
                        pass
                    return False

                time.sleep(self.poll_interval_sec)

    def release(self) -> None:
        if not self._locked:
            return
        try:
            if self._fh is not None:
                if _IS_WINDOWS:
                    try:
                        self._fh.seek(0)
                    except Exception:
                        pass
                    try:
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    try:
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
        finally:
            try:
                if self._fh is not None:
                    self._fh.close()
            except Exception:
                pass
            self._fh = None
            self._locked = False

    def __enter__(self) -> "InterProcessFileLock":
        ok = self.acquire()
        if not ok:
            raise LockError(f"Could not acquire lock: {self.path}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


_LOCAL_MUTEXES: Dict[str, threading.Lock] = {}
_LOCAL_MUTEXES_GUARD = threading.Lock()


def _get_local_mutex(key: str) -> threading.Lock:
    with _LOCAL_MUTEXES_GUARD:
        lk = _LOCAL_MUTEXES.get(key)
        if lk is None:
            lk = threading.Lock()
            _LOCAL_MUTEXES[key] = lk
        return lk


def atomic_append_jsonl(
    jsonl_path: str,
    record: Dict[str, Any],
    *,
    lock_path: Optional[str] = None,
    ensure_fsync: bool = True,
) -> None:
    """
    Safe append of one JSON object to JSONL:
    - in-process mutex (thread safety)
    - inter-process lock (multi-process safety)
    - flush + fsync (best-effort)
    """
    if lock_path is None:
        lock_path = jsonl_path + ".lock"

    os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)

    local_mutex = _get_local_mutex(jsonl_path)
    with local_mutex:
        with InterProcessFileLock(lock_path):
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            with open(jsonl_path, "a", encoding="utf-8", newline="\n") as f:
                f.write(line + "\n")
                f.flush()
                if ensure_fsync:
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
