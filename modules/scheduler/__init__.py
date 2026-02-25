# -*- coding: utf-8 -*-
"""modules.scheduler - package-sovmestimost.
MOSTY: (yavnyy) watcher.WatchConfig → re-export; (skrytye) ENV→planirovschik, fayly→ochered.
ZEMNOY ABZATs: nalichie __init__ ustranyaet sboi importa na Windows, when usercustomize ne srabotal.
# c=a+b"""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:  # re-export if there is a module
    from .watcher import WatchConfig  # type: ignore  # noqa: F401
except Exception:
    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class WatchConfig:  # type: ignore[no-redef]
        inbox_dir: str = "data/inbox"
        max_bytes: int = 16 * 1024 * 1024
        limit_files: int = 100
        enable_chunking: bool = True
        chunk_size: int = 4 * 1024 * 1024
        pattern: str = "*"
        plan_file: Optional[str] = None