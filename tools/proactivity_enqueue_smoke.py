# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage import agent_queue
from modules.proactivity import state_store
from modules.proactivity.executor import run_once
from modules.runtime import execution_window
from modules.volition.journal import journal_path


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _count_run_lines(garage_root: Path) -> int:
    agents_root = (garage_root / "agents").resolve()
    if not agents_root.exists():
        return 0
    n = 0
    for path in agents_root.rglob("runs.jsonl"):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        n += 1
        except Exception:
            continue
    return n


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="ester_proactivity_enqueue_smoke_")).resolve()
    persist_dir = (tmp_root / "persist").resolve()
    garage_root = (tmp_root / "garage").resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    garage_root.mkdir(parents=True, exist_ok=True)

    env_keys = [
        "PERSIST_DIR",
        "GARAGE_ROOT",
        "ESTER_VOLITION_SLOT",
        "ESTER_VOLITION_ALLOWED_HOURS",
        "ESTER_ALLOW_OUTBOUND_NETWORK",
        "ESTER_ORACLE_ENABLE",
        "ESTER_PROACTIVITY_ENQUEUE_ENABLED",
        "ESTER_PROACTIVITY_REAL_ACTIONS_ENABLED",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}

    os.environ["PERSIST_DIR"] = str(persist_dir)
    os.environ["GARAGE_ROOT"] = str(garage_root)
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "0"
    os.environ["ESTER_PROACTIVITY_ENQUEUE_ENABLED"] = "1"
    os.environ["ESTER_PROACTIVITY_REAL_ACTIONS_ENABLED"] = "1"

    try:
        cur = execution_window.current_window()
        if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
            execution_window.close_window(str(cur.get("window_id") or ""), actor="ester:smoke", reason="reset")
        cur2 = execution_window.current_window()
        window_closed = not bool(cur2.get("open"))

        seed = state_store.queue_add(
            title="Iter42 enqueue smoke initiative",
            text="build plan and enqueue only",
            priority="normal",
            source="tools.proactivity_enqueue_smoke",
            meta={"iter": 42, "smoke": True},
        )

        before_state = agent_queue.fold_state()
        queue_before = int(before_state.get("live_total") or 0)
        runs_before = _count_run_lines(garage_root)

        rep = run_once(
            dry=False,
            mode="enqueue",
            max_work_ms=3000,
            max_queue_size=100,
            cooldown_sec=0,
        )

        after_state = agent_queue.fold_state()
        queue_after = int(after_state.get("live_total") or 0)
        runs_after = _count_run_lines(garage_root)

        qid = str(rep.get("enqueue_id") or "")
        queue_events = _read_jsonl(agent_queue.queue_path())
        executed_events = [
            row
            for row in queue_events
            if str(row.get("queue_id") or "") == qid and str(row.get("type") or "") in {"claim", "start", "done", "fail"}
        ]

        decisions = _read_jsonl(journal_path())
        chain_id = str(rep.get("chain_id") or "")
        steps = {
            str(row.get("step") or "")
            for row in decisions
            if (not chain_id) or (str(row.get("chain_id") or "") == chain_id)
        }

        has_plan = "proactivity.plan" in steps
        has_create = "agent.create" in steps
        has_enqueue = "agent.queue.enqueue" in steps

        ok = (
            bool(window_closed)
            and bool(seed.get("ok"))
            and bool(rep.get("ok"))
            and (str(rep.get("mode") or "") == "enqueue")
            and (queue_after > queue_before)
            and bool(qid)
            and (runs_after == runs_before)
            and (len(executed_events) == 0)
            and has_plan
            and has_create
            and has_enqueue
        )

        out = {
            "ok": ok,
            "tmp_root": str(tmp_root),
            "window_closed": window_closed,
            "seed": seed,
            "run": rep,
            "queue_before": queue_before,
            "queue_after": queue_after,
            "enqueue_id": qid,
            "runs_before": runs_before,
            "runs_after": runs_after,
            "executed_events": len(executed_events),
            "journal_path": str(journal_path()),
            "volition_steps": sorted(list(steps)),
            "has_plan": has_plan,
            "has_create": has_create,
            "has_enqueue": has_enqueue,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
