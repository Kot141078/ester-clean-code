# -*- coding: utf-8 -*-
"""
modules.scheduler.watcher — konfiguratsiya votchera + planovye tiki.
# c=a+b
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@dataclass
class WatchConfig:
    inbox_dir: str = "data/inbox"
    max_bytes: int = 16 * 1024 * 1024
    limit_files: int = 100
    enable_chunking: bool = True
    chunk_size: int = 4 * 1024 * 1024
    pattern: str = "*"
    plan_file: Optional[str] = None

def plan_tick(cfg: WatchConfig | None = None) -> Dict[str, Any]:
    cfg = cfg or WatchConfig()
    return {"ok": True, "inbox": cfg.inbox_dir}

def apply_tick(cfg: WatchConfig | None = None) -> Dict[str, Any]:
    # Semantika: takoy zhe «pustoy» tik, chtoby ne padali routy UI-planirovschika
    return plan_tick(cfg)