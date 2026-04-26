# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from typing import Any, Dict, Iterable, List

try:
    from modules.memory.profile_snapshot import list_known_user_ids, load_profile_snapshot  # type: ignore
except Exception:
    list_known_user_ids = None  # type: ignore
    load_profile_snapshot = None  # type: ignore

try:
    from modules.memory.user_facts_store import load_user_facts as _load_user_facts  # type: ignore
except Exception:
    _load_user_facts = None  # type: ignore


_STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "по", "не", "но", "что", "это", "как", "из",
    "the", "and", "for", "with", "from", "this", "that", "user", "chat",
}


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _consolidation_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "consolidation")


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(text: str) -> List[str]:
    toks = re.findall(r"[0-9A-Za-zА-Яа-яЁё_]+", _normalize_text(text).lower())
    return [tok for tok in toks if len(tok) >= 3 and tok not in _STOPWORDS]


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run(limit_users: int = 50) -> Dict[str, Any]:
    user_ids = list(list_known_user_ids(limit=limit_users) or []) if callable(list_known_user_ids) else []
    token_counter: Counter[str] = Counter()
    promotion_candidates: List[Dict[str, Any]] = []
    facts_total = 0

    for user_id in user_ids:
        snapshot = load_profile_snapshot(user_id) if callable(load_profile_snapshot) else {}
        facts = list(_load_user_facts(user_id, include_legacy=False) or []) if callable(_load_user_facts) else []
        facts_total += len(facts)
        texts: List[str] = list(facts)
        summary = _normalize_text((snapshot or {}).get("summary") or "")
        if summary:
            texts.append(summary)
        for text in texts:
            token_counter.update(_tokens(text))
        promotion_candidates.append(
            {
                "user_id": str(user_id),
                "display_name": str((snapshot or {}).get("display_name") or ""),
                "summary": summary,
                "top_facts": [str(item) for item in facts[:3]],
            }
        )

    report = {
        "schema": "ester.memory.semantic_consolidation.v1",
        "ts": int(time.time()),
        "users_count": len(user_ids),
        "facts_count": facts_total,
        "top_terms": [{"term": term, "count": count} for term, count in token_counter.most_common(20)],
        "promotion_candidates": promotion_candidates[: max(1, min(limit_users, 25))],
    }

    base = _consolidation_dir()
    stem = time.strftime("%Y%m%d_%H%M%S", time.localtime(report["ts"]))
    json_path = os.path.join(base, f"semantic_consolidation_{stem}.json")
    latest_path = os.path.join(base, "latest.json")
    history_path = os.path.join(base, "history.jsonl")
    _write_json(json_path, report)
    _write_json(latest_path, report)
    _append_jsonl(history_path, report)
    try:
        from modules.memory import memory_index  # type: ignore

        memory_index.ensure_materialized()
    except Exception:
        pass
    return {"ok": True, "path": json_path, "latest_path": latest_path, "history_path": history_path, "report": report}


def latest() -> Dict[str, Any]:
    path = os.path.join(_consolidation_dir(), "latest.json")
    if not os.path.exists(path):
        return {"ok": False, "error": "not_found"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return {"ok": True, "report": data}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


__all__ = ["latest", "run"]
