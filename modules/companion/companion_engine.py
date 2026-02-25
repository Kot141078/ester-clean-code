# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.companion import outbox
from modules.volition import journal as volition_journal

_LOCK = threading.RLock()


def _persist_dir() -> Path:
    root = (os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    p = (_persist_dir() / "companion" / "state.json").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        try:
            p.write_text(
                json.dumps(
                    {
                        "last_tick": None,
                        "last_ok": None,
                        "last_error": "",
                        "last_explained_chain_id": "",
                        "seen_decision_ids": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass
    return p


def _load_state() -> Dict[str, Any]:
    p = _state_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("bad_state")
    except Exception:
        raw = {
            "last_tick": None,
            "last_ok": None,
            "last_error": "",
            "last_explained_chain_id": "",
            "seen_decision_ids": [],
        }
    raw.setdefault("last_tick", None)
    raw.setdefault("last_ok", None)
    raw.setdefault("last_error", "")
    raw.setdefault("last_explained_chain_id", "")
    raw.setdefault("seen_decision_ids", [])
    if not isinstance(raw["seen_decision_ids"], list):
        raw["seen_decision_ids"] = []
    return raw


def _save_state(state: Dict[str, Any]) -> None:
    p = _state_path()
    payload = json.dumps(dict(state or {}), ensure_ascii=False, indent=2)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(p)
        return
    except Exception:
        pass
    try:
        p.write_text(payload, encoding="utf-8")
    except Exception:
        return


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_message_from_event(event: Dict[str, Any]) -> str:
    e = dict(event or {})
    chain = str(e.get("chain_id") or "").strip()
    action = str(e.get("action_kind") or e.get("related_action") or "").strip()
    reason = str(e.get("reason") or e.get("reason_code") or "").strip()
    allowed = e.get("allowed")
    if isinstance(allowed, bool):
        status = "razresheno" if allowed else "otkloneno"
        if action:
            return f"YuZF0ZZsch Action ZZF1ZZ: ZZF2ZZ. Reason: ZFzZZ."
        return f"YuZF0ZZsch Solution: ZZF1ZZ. Reason: ZZF2ZZ."
    if action:
        return f"YuZF0ZZsch Action ZZF1ZZ has been completed. ZZF2ZZ"
    return f"YuZF0ZZsch Status update. ZZF1ZZ"


def emit_decision_note(chain_id: str, decision: Dict[str, Any], why: str = "") -> Dict[str, Any]:
    dec = dict(decision or {})
    event = {
        "chain_id": str(chain_id or dec.get("chain_id") or ""),
        "action_kind": str(dec.get("action_kind") or ""),
        "reason": str(why or dec.get("reason") or dec.get("reason_code") or ""),
        "allowed": dec.get("allowed"),
        "related_action": str(dec.get("action_kind") or ""),
    }
    text = build_message_from_event(event)
    return outbox.enqueue(
        kind="decision.note",
        text=text,
        meta={"reason": event["reason"], "allowed": event.get("allowed")},
        chain_id=event["chain_id"],
        related_action=event["related_action"],
    )


def tick_once(max_messages: int = 3, tail_n: int = 30) -> Dict[str, Any]:
    lim = max(0, int(max_messages or 0))
    if lim == 0:
        lim = 3
    lookback = max(1, int(tail_n or 1))

    with _LOCK:
        st = _load_state()
        seen = [str(x) for x in list(st.get("seen_decision_ids") or []) if str(x).strip()]
        seen_set = set(seen)

        emitted: List[Dict[str, Any]] = []
        err = ""
        try:
            rows = list(volition_journal.tail(lookback))
            for row in rows:
                rid = str(row.get("id") or "").strip()
                if not rid or rid in seen_set:
                    continue
                note = emit_decision_note(str(row.get("chain_id") or ""), row, str(row.get("reason") or ""))
                if note.get("ok"):
                    emitted.append(note)
                    seen.append(rid)
                    seen_set.add(rid)
                    st["last_explained_chain_id"] = str(row.get("chain_id") or "")
                if len(emitted) >= lim:
                    break
            st["last_ok"] = True
            st["last_error"] = ""
        except Exception as exc:
            err = f"{exc.__class__.__name__}: {exc}"
            st["last_ok"] = False
            st["last_error"] = err

        st["last_tick"] = _now_iso()
        st["seen_decision_ids"] = seen[-500:]
        _save_state(st)

    return {
        "ok": (err == ""),
        "emitted": len(emitted),
        "messages": emitted,
        "last_tick": st.get("last_tick"),
        "last_ok": st.get("last_ok"),
        "last_error": st.get("last_error"),
        "last_explained_chain_id": st.get("last_explained_chain_id"),
        "state_path": str(_state_path()),
    }


def status() -> Dict[str, Any]:
    with _LOCK:
        st = _load_state()
    return {
        "ok": True,
        "last_tick": st.get("last_tick"),
        "last_ok": st.get("last_ok"),
        "last_error": st.get("last_error"),
        "last_explained_chain_id": st.get("last_explained_chain_id"),
    }


__all__ = ["build_message_from_event", "emit_decision_note", "tick_once", "status"]

