# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PATH = os.getenv("ESTER_P2P_STATE_FILE", os.path.join("data", "p2p_offsets.json"))
_lock = threading.RLock()


def _ensure_dir():
    d = os.path.dirname(_PATH)
    if d:
        os.makedirs(d, exist_ok=True)


def _load() -> Dict[str, Any]:
    _ensure_dir()
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(obj: Dict[str, Any]) -> None:
    _ensure_dir()
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PATH)


def get_peer_state(peer_url: str) -> Dict[str, Any]:
    with _lock:
        db = _load()
        return db.get(peer_url, {})


def set_peer_state(peer_url: str, state: Dict[str, Any]) -> None:
    with _lock:
        db = _load()
        db[peer_url] = state
        _save(db)


def get_last_clock(peer_url: str) -> Optional[int]:
    st = get_peer_state(peer_url)
    c = st.get("last_clock")
    if isinstance(c, int):
        return c
    return None


def set_last_clock(peer_url: str, clock: int) -> None:
    st = get_peer_state(peer_url)
    st["last_clock"] = int(clock)
    set_peer_state(peer_url, st)


def set_last_leaf_root(peer_url: str, root: str) -> None:
    st = get_peer_state(peer_url)
    st["last_leaf_root"] = str(root)
    set_peer_state(peer_url, st)


def get_last_leaf_root(peer_url: str) -> Optional[str]:
    st = get_peer_state(peer_url)
    r = st.get("last_leaf_root")
    return str(r) if r else None
