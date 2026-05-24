# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _default_path() -> str:
    root = Path(os.getenv("PERSIST_DIR") or Path.cwd() / "data")
    return str(root / "hypothesis.jsonl")


def _stable_id(text: str, topic: str) -> str:
    raw = f"{topic}\n{text}".encode("utf-8")
    return "h_" + hashlib.sha1(raw).hexdigest()[:16]


def _tags(value: Optional[Iterable[Any]]) -> List[str]:
    out: List[str] = []
    for item in value or []:
        tag = str(item or "").strip()
        if tag and tag not in out:
            out.append(tag)
    return out


def _normalize_text(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("Idea:"):
        return "Ideya:" + value[len("Idea:") :]
    return value


class HypothesisStore:
    """JSON-backed compatibility store for legacy memory.hypothesis_store imports."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = str(path or _default_path())
        self._items: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        self._items = {}
        p = Path(self.path)
        if not p.exists():
            return
        try:
            raw = p.read_text(encoding="utf-8").strip()
        except Exception:
            return
        if not raw:
            return

        rows: List[Any] = []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                rows = parsed
            elif isinstance(parsed, dict):
                if parsed.get("id"):
                    rows = [parsed]
                else:
                    rows = list(parsed.get("items") or parsed.get("records") or [])
        except Exception:
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue

        for row in rows:
            if isinstance(row, dict) and str(row.get("id") or ""):
                item = self._normalize_item(row)
                self._items[str(item["id"])] = item

    def _save(self) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for item in sorted(self._items.values(), key=lambda row: str(row.get("id") or "")):
                f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, p)

    def _normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        text = _normalize_text(str(item.get("text") or ""))
        topic = str(item.get("topic") or "")
        item_id = str(item.get("id") or _stable_id(text, topic))
        used_count = int(item.get("used_count") or item.get("uses") or 0)
        used = bool(item.get("used") or used_count > 0)
        return {
            "id": item_id,
            "text": text,
            "topic": topic,
            "tags": _tags(item.get("tags") or []),
            "score": float(item.get("score") if item.get("score") is not None else 0.5),
            "mtime": float(item.get("mtime") or time.time()),
            "used": used,
            "used_count": used_count,
            "uses": used_count,
        }

    def add(
        self,
        text: str,
        topic: str = "",
        tags: Optional[Iterable[Any]] = None,
        score: float = 0.5,
        **_: Any,
    ) -> str:
        norm_text = _normalize_text(text)
        norm_topic = str(topic or "")
        item_id = _stable_id(norm_text, norm_topic)
        now = time.time()
        old = self._items.get(item_id)
        if old is None:
            self._items[item_id] = self._normalize_item(
                {
                    "id": item_id,
                    "text": norm_text,
                    "topic": norm_topic,
                    "tags": _tags(tags),
                    "score": float(score),
                    "mtime": now,
                }
            )
        else:
            merged_tags = _tags([*old.get("tags", []), *_tags(tags)])
            old.update(
                {
                    "text": norm_text,
                    "topic": norm_topic,
                    "tags": merged_tags,
                    "score": float(score),
                    "mtime": now,
                }
            )
            self._items[item_id] = self._normalize_item(old)
        self._save()
        return item_id

    def get(self, hid: str) -> Optional[Dict[str, Any]]:
        item = self._items.get(str(hid or ""))
        return dict(item) if item else None

    def list(self, topic: Optional[str] = None, limit: int = 100, **_: Any) -> List[Dict[str, Any]]:
        rows = list(self._items.values())
        if topic is not None:
            rows = [row for row in rows if str(row.get("topic") or "") == str(topic)]
        rows.sort(key=lambda row: float(row.get("mtime") or 0.0), reverse=True)
        return [dict(row) for row in rows[: max(0, int(limit or 100))]]

    def delete(self, hid: str) -> bool:
        key = str(hid or "")
        if key not in self._items:
            return False
        self._items.pop(key, None)
        self._save()
        return True

    def feedback(
        self,
        hid: str,
        used: Optional[bool] = None,
        delta_score: Optional[float] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        item = self._items.get(str(hid or ""))
        if item is None:
            return {"ok": False, "error": "not_found", "id": hid}
        if used is not None:
            item["used"] = bool(used)
            if bool(used):
                item["used_count"] = int(item.get("used_count") or 0) + 1
                item["uses"] = int(item.get("used_count") or 0)
        if delta_score is not None:
            item["score"] = float(item.get("score") or 0.0) + float(delta_score)
        item["mtime"] = time.time()
        self._items[str(item["id"])] = self._normalize_item(item)
        self._save()
        return {"ok": True, "item": dict(self._items[str(item["id"])])}


__all__ = ["HypothesisStore"]
