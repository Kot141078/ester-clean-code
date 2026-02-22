# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.dreams.store import DreamStore

_KEYWORDS = (
    "todo",
    "fix",
    "need",
    "later",
    "next",
    "issue",
    "bug",
    "unresolved",
    "sdelat",
    "nado",
    "potom",
)


def _resolve_persist_dir(persist_dir: Optional[str]) -> Path:
    base = str(persist_dir or os.getenv("PERSIST_DIR") or "").strip()
    if not base:
        base = str((Path.cwd() / "data").resolve())
    out = Path(base).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def _now_iso(ts: Optional[float] = None) -> str:
    value = float(ts if ts is not None else time.time())
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _safe_agent_name(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower())
    base = re.sub(r"_+", "_", base).strip("_")
    if not base:
        base = "initiative"
    return ("auto_" + base)[:48]


class InitiativeEngine:
    def __init__(self, persist_dir: Optional[str] = None) -> None:
        self.persist_dir = _resolve_persist_dir(persist_dir)
        self.queue_path = (self.persist_dir / "initiatives" / "queue.jsonl").resolve()
        self.state_path = (self.persist_dir / "initiatives" / "state.json").resolve()
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.dream_store = DreamStore(persist_dir=str(self.persist_dir))

    def _append_queue(self, row: Dict[str, Any]) -> None:
        with self.queue_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _queue_size(self) -> int:
        if not self.queue_path.exists():
            return 0
        n = 0
        try:
            with self.queue_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        n += 1
        except Exception:
            return 0
        return n

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
        return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False, indent=2)
        tmp = self.state_path.with_suffix(".json.tmp")
        try:
            tmp.write_text(payload, encoding="utf-8")
            try:
                tmp.replace(self.state_path)
                return
            except Exception:
                pass
        except Exception:
            pass
        try:
            with self.state_path.open("w", encoding="utf-8") as f:
                f.write(payload)
        except Exception:
            pass

    def _extract_title(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        if not cleaned:
            return "Follow up memory signal"
        return cleaned[:80]

    def _build_candidates(
        self,
        recent: List[Dict[str, Any]],
        dream_hints: List[Dict[str, Any]],
        max_items: int,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen = set()
        for rec in recent:
            text = str(rec.get("text") or "").strip()
            if not text:
                continue
            low = text.lower()
            if not any(k in low for k in _KEYWORDS):
                continue
            key = text[:160].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "title": self._extract_title(text),
                    "text": text[:240],
                    "priority": "normal",
                    "source": "recent_window",
                    "source_id": str(rec.get("id") or ""),
                    "proposal": {
                        "type": "create_agent_plan",
                        "spec": {
                            "name": _safe_agent_name(text[:64]),
                            "goal": self._extract_title(text),
                            "allowed_actions": ["memory.add_note", "files.sandbox_write", "files.sha256_verify"],
                            "budgets": {"max_actions": 4, "max_work_ms": 2000, "window": 60, "est_work_ms": 250},
                            "owner": "proactivity",
                            "oracle_policy": {"allow_remote": False},
                        },
                        "plan": {
                            "steps": [
                                {
                                    "action_id": "memory.add_note",
                                    "args": {
                                        "text": f"initiative candidate: {self._extract_title(text)}",
                                        "tags": ["initiative", "proposal"],
                                        "source": "initiative_engine",
                                    },
                                }
                            ]
                        },
                    },
                }
            )
            if len(out) >= max_items:
                return out

        for hint in dream_hints:
            text = str(hint.get("text") or "").strip()
            if not text:
                continue
            key = ("dream:" + text[:160]).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "title": "Review dream insight",
                    "text": text[:240],
                    "priority": "low",
                    "source": "dream_hint",
                    "source_id": str(hint.get("id") or ""),
                    "proposal": {
                        "type": "create_agent_plan",
                        "spec": {
                            "name": _safe_agent_name("dream_" + text[:48]),
                            "goal": "Review dream insight and capture memory note",
                            "allowed_actions": ["memory.add_note", "files.sandbox_write", "files.sha256_verify"],
                            "budgets": {"max_actions": 4, "max_work_ms": 2000, "window": 60, "est_work_ms": 250},
                            "owner": "proactivity",
                            "oracle_policy": {"allow_remote": False},
                        },
                        "plan": {
                            "steps": [
                                {
                                    "action_id": "memory.add_note",
                                    "args": {
                                        "text": f"dream initiative: {text[:180]}",
                                        "tags": ["dream", "initiative", "proposal"],
                                        "source": "initiative_engine",
                                    },
                                }
                            ]
                        },
                    },
                }
            )
            if len(out) >= max_items:
                return out
        return out

    def run_once(
        self,
        memory_bus: Any,
        now_ts: Optional[float] = None,
        budgets: Optional[Dict[str, Any]] = None,
        dry: bool = False,
    ) -> Dict[str, Any]:
        ts = float(now_ts if now_ts is not None else time.time())
        budgets = dict(budgets or {})
        recent_limit = max(1, int(budgets.get("window", 60) or 60))
        max_items = max(1, int(budgets.get("max_items", 5) or 5))

        try:
            recent = list(memory_bus.get_recent_window(limit=recent_limit))
            hints = self.dream_store.tail(limit=3)
            candidates = self._build_candidates(recent, hints, max_items=max_items)

            created: List[Dict[str, Any]] = []
            for row in candidates:
                item = {
                    "id": "initiative_" + uuid.uuid4().hex,
                    "ts": _now_iso(ts),
                    "title": row["title"],
                    "text": row["text"],
                    "priority": row["priority"],
                    "status": "queued",
                    "source": row["source"],
                    "source_id": row["source_id"],
                }
                if isinstance(row.get("proposal"), dict):
                    item["proposal"] = dict(row.get("proposal") or {})
                if not dry:
                    self._append_queue(item)
                created.append(item)

            queue_size = self._queue_size()
            state = {
                "last_run": _now_iso(ts),
                "last_ok": True,
                "last_error": "",
                "queue_size": queue_size,
                "created_count": len(created),
                "path": str(self.queue_path),
            }
            self._save_state(state)
            return {"ok": True, "created": created, **state, "stored": bool(not dry)}
        except Exception as exc:
            err = str(exc)
            queue_size = self._queue_size()
            state = {
                "last_run": _now_iso(ts),
                "last_ok": False,
                "last_error": err,
                "queue_size": queue_size,
                "created_count": 0,
                "path": str(self.queue_path),
            }
            self._save_state(state)
            return {"ok": False, "error": err, **state, "stored": False}

    def status(self) -> Dict[str, Any]:
        state = self._load_state()
        state.setdefault("last_run", None)
        state.setdefault("last_ok", None)
        state.setdefault("last_error", "")
        state["queue_size"] = self._queue_size()
        state["path"] = str(self.queue_path)
        state["state_path"] = str(self.state_path)
        state["ok"] = True
        return state
