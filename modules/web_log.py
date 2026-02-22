#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_log.py — minimal "internet ampere-meter" for an Entity node.

- JSONL append-only logging for any web request:
    1) start_request() writes status=pending
    2) finish_request() writes status=ok/error (same request_id)

- Budget gate in WEB_BUDGET.json:
    warn >= 70%
    soft_stop >= 85%   (web only with explicit override)
    hard_stop >= 95%   (block unless explicit override)

- Optional hash-chain ("seal") for every written line in WEBLOG.sha256chain.jsonl:
    entry_hash = sha256(canonical_json(record) + prev_hash)

No external dependencies. Safe for closed-box; no web calls here.
"""

from __future__ import annotations

import base64
import dataclasses
import datetime as _dt
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ---------------------------
# Exceptions
# ---------------------------

class WebLogError(RuntimeError):
    """Base error for web logging and budget operations."""


class WebBudgetExceeded(WebLogError):
    """Raised when budget gate blocks non-overridden web usage."""
    def __init__(self, message: str, gate: str, pct: float):
        super().__init__(message)
        self.gate = gate
        self.pct = pct


# ---------------------------
# Helpers: time, json, hashing
# ---------------------------

def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> str:
    """
    Deterministic JSON for hashing:
    - sort keys
    - no spaces
    - UTF-8 safe
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    ensure_parent_dir(path)
    line = canonical_json(record) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)


def read_last_nonempty_line(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    # Efficient tail read without loading whole file
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size == 0:
            return None
        # read last 8KB
        step = min(8192, size)
        f.seek(-step, os.SEEK_END)
        chunk = f.read(step)
    lines = chunk.splitlines()
    if not lines:
        return None
    # Return last non-empty line
    for b in reversed(lines):
        if b.strip():
            return b.decode("utf-8", errors="replace")
    return None


# ---------------------------
# ULID (Crockford Base32) without deps
# ---------------------------

_CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def _encode_crockford32(data: bytes) -> str:
    # Encode bytes as base32 (crockford) without padding
    # We'll convert to int and then base32.
    n = int.from_bytes(data, "big")
    if n == 0:
        return "0"
    out = []
    while n > 0:
        n, r = divmod(n, 32)
        out.append(_CROCKFORD32[r])
    out.reverse()
    return "".join(out)

def ulid() -> str:
    """
    ULID-like string:
    - 48-bit timestamp (ms)
    - 80-bit randomness
    Total 128 bits -> 26 chars in Crockford base32 (commonly).
    We'll generate 16 bytes and encode, then left-pad to 26 chars.
    """
    ts_ms = int(time.time() * 1000)
    ts_bytes = ts_ms.to_bytes(6, "big", signed=False)  # 48-bit
    rnd_bytes = secrets.token_bytes(10)               # 80-bit
    raw = ts_bytes + rnd_bytes                        # 16 bytes
    s = _encode_crockford32(raw)
    return s.rjust(26, "0")[:26]


# ---------------------------
# Budget model
# ---------------------------

DEFAULT_BUDGET = {
    "provider": "serpapi",
    "period": "monthly",
    "limit": 250,
    "used": 0,
    "thresholds": {"warn": 0.70, "soft_stop": 0.85, "hard_stop": 0.95},
    "mode": "offline-first",  # offline-first | web-first
    "policy_version": "web-policy-v0.1",
    "updated_utc": "1970-01-01T00:00:00Z"
}

def load_budget(path: Path) -> Dict[str, Any]:
    if not path.exists():
        ensure_parent_dir(path)
        data = dict(DEFAULT_BUDGET)
        data["updated_utc"] = utc_now_iso()
        path.write_text(canonical_json(data) + "\n", encoding="utf-8")
        return data
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise WebLogError(f"Failed to read budget file: {path}: {e}")

def save_budget(path: Path, data: Dict[str, Any]) -> None:
    data = dict(data)
    data["updated_utc"] = utc_now_iso()
    ensure_parent_dir(path)
    path.write_text(canonical_json(data) + "\n", encoding="utf-8")

def budget_gate(budget: Dict[str, Any], planned_cost: int = 1) -> Tuple[str, float, int]:
    """
    Returns (gate, pct_after, used_after)
      gate: ok | warn | soft_stop | hard_stop | over
    """
    limit = int(budget.get("limit", 0) or 0)
    used = int(budget.get("used", 0) or 0)
    used_after = used + max(0, int(planned_cost))
    pct_after = (used_after / limit) if limit > 0 else 1.0

    thr = budget.get("thresholds", {}) or {}
    warn = float(thr.get("warn", 0.70))
    soft = float(thr.get("soft_stop", 0.85))
    hard = float(thr.get("hard_stop", 0.95))

    if limit <= 0:
        return ("hard_stop", 1.0, used_after)
    if used_after > limit:
        return ("over", pct_after, used_after)
    if pct_after >= hard:
        return ("hard_stop", pct_after, used_after)
    if pct_after >= soft:
        return ("soft_stop", pct_after, used_after)
    if pct_after >= warn:
        return ("warn", pct_after, used_after)
    return ("ok", pct_after, used_after)


# ---------------------------
# Hash-chain for "seal"
# ---------------------------

def chain_append(chain_path: Path, request_id: str, record: Dict[str, Any]) -> Dict[str, str]:
    """
    Append an entry to WEBLOG.sha256chain.jsonl:
      prev_hash + entry_hash for this record
    """
    ensure_parent_dir(chain_path)

    prev_hash = "0" * 64
    last = read_last_nonempty_line(chain_path)
    if last:
        try:
            last_obj = json.loads(last)
            prev_hash = str(last_obj.get("entry_hash", prev_hash))
            if len(prev_hash) != 64:
                prev_hash = "0" * 64
        except Exception:
            prev_hash = "0" * 64

    payload = canonical_json(record) + prev_hash
    entry_hash = sha256_hex(payload)

    chain_rec = {
        "ts_utc": utc_now_iso(),
        "request_id": request_id,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash
    }
    append_jsonl(chain_path, chain_rec)
    return {"prev_hash": prev_hash, "entry_hash": entry_hash}


# ---------------------------
# Public API
# ---------------------------

def web_marker(request_id: Optional[str]) -> str:
    return f"[WEB:{request_id}]" if request_id else "[WEB:none]"


@dataclasses.dataclass
class WebLoggerConfig:
    base_dir: Path
    node_id: str
    actor: str
    provider: str = "serpapi"
    closed_box: bool = False
    enable_hash_chain: bool = True

    weblog_rel: str = "evidence/web/WEBLOG.jsonl"
    chain_rel: str = "evidence/web/WEBLOG.sha256chain.jsonl"
    budget_rel: str = "evidence/web/WEB_BUDGET.json"


class WebLogger:
    def __init__(self, cfg: WebLoggerConfig):
        self.cfg = cfg
        self.weblog_path = (cfg.base_dir / cfg.weblog_rel).resolve()
        self.chain_path = (cfg.base_dir / cfg.chain_rel).resolve()
        self.budget_path = (cfg.base_dir / cfg.budget_rel).resolve()

    def _common(self) -> Dict[str, Any]:
        return {
            "ts_utc": utc_now_iso(),
            "actor": self.cfg.actor,
            "node_id": self.cfg.node_id,
            "provider": self.cfg.provider,
            "closed_box": bool(self.cfg.closed_box),
        }

    def start_request(
        self,
        query_text: str,
        intent: str = "search",
        purpose: Optional[str] = None,
        domains_allowlist: Optional[List[str]] = None,
        recency_days: Optional[int] = None,
        cost_estimated: int = 1,
        override_soft_stop: bool = False,
        override_hard_stop: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Creates a pending record in WEBLOG.jsonl.
        Returns (request_id, record)
        """
        request_id = ulid()
        budget = load_budget(self.budget_path)

        gate, pct_after, used_after = budget_gate(budget, planned_cost=cost_estimated)

        # Gate logic
        if gate in ("hard_stop", "over") and not override_hard_stop:
            raise WebBudgetExceeded(
                f"Web budget gate={gate}: {used_after}/{budget.get('limit')} ({pct_after*100:.1f}%). Blocked.",
                gate=gate, pct=pct_after
            )
        if gate == "soft_stop" and not override_soft_stop:
            raise WebBudgetExceeded(
                f"Web budget gate=soft_stop: {used_after}/{budget.get('limit')} ({pct_after*100:.1f}%). Blocked without explicit override.",
                gate=gate, pct=pct_after
            )

        record: Dict[str, Any] = {}
        record.update(self._common())
        record.update({
            "request_id": request_id,
            "intent": intent,
            "purpose": purpose,
            "query_text": query_text,
            "query_sha256": sha256_hex(query_text),
            "domains_allowlist": domains_allowlist or [],
            "recency_days": recency_days,
            "status": "pending",
            "cached": False,
            "cost": {"unit": "search", "estimated": int(cost_estimated), "actual": None},
            "budget": {
                "limit": int(budget.get("limit", 0) or 0),
                "used_before": int(budget.get("used", 0) or 0),
                "used_after_planned": int(used_after),
                "pct_after_planned": round(pct_after * 100, 2),
                "policy_gate": gate,
                "override_soft_stop": bool(override_soft_stop),
                "override_hard_stop": bool(override_hard_stop),
            },
        })

        if extra:
            record["extra"] = extra

        append_jsonl(self.weblog_path, record)
        if self.cfg.enable_hash_chain:
            chain_append(self.chain_path, request_id=request_id, record=record)

        return request_id, record

    def finish_request(
        self,
        request_id: str,
        status: str,
        cached: bool = False,
        results: Optional[Dict[str, Any]] = None,
        cost_actual: int = 1,
        latency_ms: Optional[int] = None,
        error: Optional[Dict[str, Any]] = None,
        update_budget: bool = True,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Writes a completion record with same request_id.
        Optionally increments budget.used by cost_actual.
        """
        if status not in ("ok", "error"):
            raise WebLogError(f"finish_request: invalid status: {status}")

        budget_before = load_budget(self.budget_path)
        used_before = int(budget_before.get("used", 0) or 0)
        limit = int(budget_before.get("limit", 0) or 0)

        # Decide if we count towards budget:
        # - cached results: typically 0 (but you can pass cost_actual=0)
        # - error: depends on provider; default counts as 1 (pass 0 if not consumed)
        inc = int(cost_actual) if update_budget else 0
        used_after = used_before + max(0, inc)
        pct_after = (used_after / limit) if limit > 0 else 1.0
        gate_after, _, _ = budget_gate({**budget_before, "used": used_after}, planned_cost=0)

        record: Dict[str, Any] = {}
        record.update(self._common())
        record.update({
            "request_id": request_id,
            "status": status,
            "cached": bool(cached),
            "latency_ms": latency_ms,
            "cost": {"unit": "search", "estimated": None, "actual": int(cost_actual)},
            "results": results or {},
            "error": error,
            "budget": {
                "limit": limit,
                "used_before": used_before,
                "used_after": used_after,
                "pct_after": round(pct_after * 100, 2),
                "policy_gate_after": gate_after,
            },
        })

        if extra:
            record["extra"] = extra

        append_jsonl(self.weblog_path, record)
        if self.cfg.enable_hash_chain:
            chain_append(self.chain_path, request_id=request_id, record=record)

        if update_budget:
            new_budget = dict(budget_before)
            new_budget["used"] = used_after
            save_budget(self.budget_path, new_budget)

        return record


# ---------------------------
# Minimal CLI demo (optional)
# ---------------------------

def _parse_args(argv: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"cmd": None}
    if len(argv) < 2:
        return out
    out["cmd"] = argv[1]
    # naive parse: --key value
    i = 2
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            out[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return out

def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    cmd = args.get("cmd")
    if not cmd:
        print("Usage:")
        print("  python web_log.py demo --base . --node ester-win --actor Ester --query \"...\"")
        print("  python web_log.py marker --id <REQUEST_ID>")
        return 2

    if cmd == "marker":
        rid = args.get("id")
        print(web_marker(rid))
        return 0

    if cmd == "demo":
        base = Path(args.get("base", ".")).resolve()
        node = str(args.get("node", "node"))
        actor = str(args.get("actor", "Ester"))
        provider = str(args.get("provider", "serpapi"))
        query = str(args.get("query", "demo query"))

        wl = WebLogger(WebLoggerConfig(base_dir=base, node_id=node, actor=actor, provider=provider))
        try:
            rid, rec0 = wl.start_request(query_text=query, purpose="demo", cost_estimated=1)
        except WebBudgetExceeded as e:
            print(f"[BLOCKED] {e}")
            return 3

        # simulate completion
        rec1 = wl.finish_request(
            request_id=rid,
            status="ok",
            cached=False,
            results={"count": 3, "top_domains": ["example.com"], "result_ids": ["demo:1", "demo:2"]},
            cost_actual=1,
            latency_ms=123
        )
        print("request_id:", rid)
        print("marker:", web_marker(rid))
        return 0

    print(f"Unknown cmd: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
