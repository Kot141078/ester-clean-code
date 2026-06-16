# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import load_config
from .policy import ALLOWED_LOW_RISK_PARAMS


def state_root(root: str | None = None) -> Path:
    return Path(root or load_config().root)


def state_paths(root: str | None = None) -> dict[str, Path]:
    base = state_root(root)
    return {
        "root": base,
        "fitness": base / "fitness.jsonl",
        "outcome_rejections": base / "outcome_rejections.jsonl",
        "witness": base / "growth_witness.jsonl",
        "candidates": base / "candidates.jsonl",
        "replay": base / "replay",
        "real_replay": base / "replay" / "real_redacted.jsonl",
        "promoted_policy": base / "promoted_policy.json",
        "rollback": base / "rollback",
        "reports": base / "reports",
    }


def ensure_layout(root: str | None = None) -> dict[str, Path]:
    paths = state_paths(root)
    for key in ("root", "replay", "rollback", "reports"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def default_policy() -> dict[str, float]:
    return {name: 0.0 for name in sorted(ALLOWED_LOW_RISK_PARAMS)}


def load_promoted_policy(root: str | None = None) -> dict[str, float]:
    path = state_paths(root)["promoted_policy"]
    if not path.exists():
        return default_policy()
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        params = obj.get("params") if isinstance(obj, dict) else obj
        if not isinstance(params, dict):
            return default_policy()
        merged = default_policy()
        for key, value in params.items():
            if key in merged and isinstance(value, (int, float)) and not isinstance(value, bool):
                merged[key] = float(value)
        return merged
    except Exception:
        return default_policy()


def write_promoted_policy(params: dict[str, float], root: str | None = None) -> Path:
    paths = ensure_layout(root)
    payload = {"schema": "ester.srlm.policy.v1", "ts": int(time.time()), "params": dict(params)}
    paths["promoted_policy"].write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2), encoding="utf-8")
    return paths["promoted_policy"]


def write_rollback_snapshot(params: dict[str, float], root: str | None = None, reason: str = "") -> Path:
    paths = ensure_layout(root)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = paths["rollback"] / f"rollback_{stamp}_{int(time.time() * 1000) % 1000:03d}.json"
    payload = {
        "schema": "ester.srlm.rollback.v1",
        "ts": int(time.time()),
        "reason": str(reason or ""),
        "params": dict(params),
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2), encoding="utf-8")
    return path


def latest_rollback(root: str | None = None) -> Path | None:
    folder = state_paths(root)["rollback"]
    if not folder.exists():
        return None
    rows = sorted(folder.glob("rollback_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def append_candidate(row: dict[str, Any], root: str | None = None) -> Path:
    paths = ensure_layout(root)
    with paths["candidates"].open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(row), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
    return paths["candidates"]


def read_jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    if limit and len(out) > limit:
        return out[-int(limit):]
    return out
