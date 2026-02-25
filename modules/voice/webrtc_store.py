# -*- coding: utf-8 -*-
"""modules.voice.webrtc_store - in-memory WebRTC store (expanded).
# c=a+b"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_STORE: Dict[str, Dict[str, Any]] = {}

def save(sid: str, offer: Dict[str, Any]) -> None:
    _STORE[sid] = {"offer": offer}
def load(sid: str) -> Dict[str, Any] | None:
    return _STORE.get(sid)
def clear(sid: str) -> None:
    _STORE.pop(sid, None)

def store_offer(sid: str, offer: Dict[str, Any]) -> None:
    save(sid, offer)
def get_offer(sid: str) -> Dict[str, Any] | None:
    item = _STORE.get(sid)
    return item.get("offer") if item else None

def store_answer(sid: str, answer: Dict[str, Any]) -> None:
    _STORE.setdefault(sid, {})["answer"] = answer
def get_answer(sid: str) -> Dict[str, Any] | None:
    item = _STORE.get(sid)
    return item.get("answer") if item else None