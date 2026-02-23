# -*- coding: utf-8 -*-
"""
security/rate_limit.py — prostoy rate-limit (per-IP, per-token) s token-baketom.

Drop-in sovmestim s kodom v dampe:
 - API: get_rate_limiter().check(ip: str, token_id: Optional[str]) -> (ok: bool, retry_after: float, info: dict)
 - ENV:
     RATE_LIMIT_PER_MIN_IP      (int, po umolchaniyu 120)
     RATE_LIMIT_PER_MIN_TOKEN   (int, po umolchaniyu 120)
     RATE_LIMIT_BURST_MULT      (float, po umolchaniyu 2.0)
     PERSIST_DIR                (katalog dlya state.json)
 - Khranilische sostoyaniya: PERSIST_DIR/rate_limit/state.json (json; best-effort)
 - Anti I/O-shtorm: zapis ne chasche N sek ili kazhdye M obnovleniy

MOSTY:
- Yavnyy: (Bezopasnost ↔ Nadezhnost) ogranichivaem chastotu, ne valya servis na vspleskakh.
- Skrytyy #1: (Inzheneriya ↔ Ekspluatatsiya) sostoyanie perezhivaet restart protsessa.
- Skrytyy #2: (Nablyudaemost ↔ Diagnostika) v info vozvraschaem vnutrennie parametry baketov.

ZEMNOY ABZATs:
Etot modul — predokhranitel: pri DDoS/skriptakh-likhoradkakh otbrasyvaet lishnee, a pri
normalnoy rabote nezameten. Rabotaet dlya kazhdogo IP i otdelno dlya kazhdogo tokena.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --------- konfig iz okruzheniya ---------

def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base

def _state_path() -> str:
    p = os.path.join(_persist_dir(), "rate_limit")
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass
    return os.path.join(p, "state.json")

def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

# --------- token-baket ---------

@dataclass
class _Bucket:
    tokens: float
    last: float

    def leak(self, rate_per_sec: float, cap: float, now: float) -> None:
        if self.last <= 0.0:
            self.last = now
            return
        dt = max(0.0, now - self.last)
        if dt > 0.0 and rate_per_sec > 0.0:
            self.tokens = min(cap, self.tokens + dt * rate_per_sec)
        self.last = now

    def take(self, amount: float, rate_per_sec: float, cap: float, now: float) -> Tuple[bool, float]:
        self.leak(rate_per_sec, cap, now)
        if self.tokens >= amount:
            self.tokens -= amount
            return True, 0.0
        # skolko zhdat do vospolneniya
        need = amount - self.tokens
        retry_after = need / rate_per_sec if rate_per_sec > 0 else 60.0
        return False, max(0.0, retry_after)

# --------- khranilische/singlton ---------

_LOCK = threading.Lock()

def _load() -> Dict[str, Dict[str, float]]:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}

def _save(state: Dict[str, Dict[str, float]]) -> None:
    try:
        tmp = _state_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, _state_path())
    except Exception:
        # best-effort: otsutstvie diska/prav ne ostanavlivaet zaprosy
        pass

class RateLimiter:
    """
    Dva nezavisimykh baketa: dlya IP i dlya tokena.
    """
    def __init__(self) -> None:
        # limity/skorosti
        per_min_ip = _env_int("RATE_LIMIT_PER_MIN_IP", 120)
        per_min_tok = _env_int("RATE_LIMIT_PER_MIN_TOKEN", 120)
        burst = max(1.0, _env_float("RATE_LIMIT_BURST_MULT", 2.0))

        # emkosti i skorosti (tokenov/sek)
        self.ip_cap = float(per_min_ip) * burst
        self.tok_cap = float(per_min_tok) * burst
        self.ip_rate = float(per_min_ip) / 60.0
        self.tok_rate = float(per_min_tok) / 60.0

        # sostoyanie
        self.state: Dict[str, Dict[str, float]] = _load()
        self._last_flush = time.time()
        self._dirty = 0
        # anti I/O-shtorm
        self._flush_sec = 2.0
        self._flush_every = 400

    # --- vnutrennee ---

    def _bucket_for(self, key: str, cap: float, rate: float) -> _Bucket:
        row = self.state.get(key)
        if not row:
            b = _Bucket(tokens=cap, last=time.time())
            self.state[key] = {"tokens": b.tokens, "last": b.last}
            return b
        return _Bucket(tokens=float(row.get("tokens", cap)), last=float(row.get("last", time.time())))

    def _store_bucket(self, key: str, b: _Bucket) -> None:
        self.state[key] = {"tokens": b.tokens, "last": b.last}
        self._dirty += 1
        now = time.time()
        if (now - self._last_flush) >= self._flush_sec or self._dirty >= self._flush_every:
            _save(self.state)
            self._last_flush = now
            self._dirty = 0

    # --- publichnoe API ---

    def check(self, ip: str, token_id: Optional[str]) -> Tuple[bool, float, dict]:
        """
        Vozvraschaet (ok, retry_after_sec, info)
        """
        now = time.time()
        ip_key = f"ip:{ip or 'unknown'}"
        tok_key = f"tok:{token_id or 'anonymous'}"

        with _LOCK:
            b_ip = self._bucket_for(ip_key, self.ip_cap, self.ip_rate)
            ok_ip, wait_ip = b_ip.take(1.0, self.ip_rate, self.ip_cap, now)
            self._store_bucket(ip_key, b_ip)

            b_tok = self._bucket_for(tok_key, self.tok_cap, self.tok_rate)
            ok_tok, wait_tok = b_tok.take(1.0, self.tok_rate, self.tok_cap, now)
            self._store_bucket(tok_key, b_tok)

        ok = ok_ip and ok_tok
        retry_after = max(wait_ip, wait_tok)
        info = {
            "ip_ok": ok_ip,
            "tok_ok": ok_tok,
            "ip_tokens": round(b_ip.tokens, 3),
            "tok_tokens": round(b_tok.tokens, 3),
            "ip_cap": self.ip_cap,
            "tok_cap": self.tok_cap,
            "ip_rate": self.ip_rate,
            "tok_rate": self.tok_rate,
            "ts": now,
        }
        return ok, retry_after, info

# --------- singleton ----------

_GLOBAL: Optional[RateLimiter] = None
_GLOBAL_CFG: Optional[tuple[str, str, str, str]] = None

def get_rate_limiter() -> RateLimiter:
    """
    Drop-in tochka vkhoda dlya routes/security_middleware.py i testov.
    """
    global _GLOBAL, _GLOBAL_CFG
    cfg = (
        os.getenv("PERSIST_DIR", ""),
        os.getenv("RATE_LIMIT_PER_MIN_IP", ""),
        os.getenv("RATE_LIMIT_PER_MIN_TOKEN", ""),
        os.getenv("RATE_LIMIT_BURST_MULT", ""),
    )
    if _GLOBAL is None or _GLOBAL_CFG != cfg:
        _GLOBAL = RateLimiter()
        _GLOBAL_CFG = cfg
    return _GLOBAL
