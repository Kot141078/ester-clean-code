# -*- coding: utf-8 -*-
"""modules/memory/structured_memory.py

StructuredMemory - “strukturirovannaya” pamyat (JSON) dlya Ester.
Khranit ne potok “mysley”, a proverennye fakty/resheniya/svodki, chtoby potom bystro izvlekat.

MOSTY (kak ty trebuesh, vnutri artefakta):
- Yavnyy most: QA → StructuredMemory (snachala proverka/filtr, potom zapis).
- Skrytyy most #1: Ashby (kibernetika) → ustoychivost kontura: stats (nablyudaemost) + compact (korrektsiya).
- Skrytyy most #2: Cover&Thomas (infoteoriya) → vysokiy SNR: dedup-okno i filtratsiya empty.
ZEMNOY ABZATs:
Eto kak zhurnal tekhobsluzhivaniya: tuda pishut “what did you do i pochemu”, and ne kazhdoe chikhanie sistemy.

Closed-box friendly: only standartnaya biblioteka, bez seti.

Format files:
{
  "records": [
     {
       "id": "...",
       "text": "...",
       "tags": ["..."],
       "kind": "fact|decision|summary|...",
       "weight": 0.5,
       "mtime": 1770...,
       "meta": { ... } #optsionalno
     }
  ],
  "alias_map": { "old_id": "new_id", ... }
}

Sovmestimost:
- Staroe: add_record(text, tags=None, weight=0.5) -> id
- Novoe: add_record(..., kind="fact", meta={...}, dedupe=True, force_save=False) -> id
- Staroe: flashback(query, k=5) -> list
- Novoe: flashback(query, k=5, top_k=None, kind=..., tags_any=..., tags_all=...) -> list"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# tokens: Latin/Cyrillic/digits, including E/e
_TOKEN_RE = re.compile(r"[A-Za-z0-9A-Yaa-yaEe]+", re.UNICODE)


def _now_ts() -> int:
    return int(time.time())


def _ensure_dir_for_file(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _default_structured_path() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    path = os.path.join(base, "structured_mem", "store.json")
    _ensure_dir_for_file(path)
    return os.path.normpath(path)


def _atomic_write_json(path: str, data: Any) -> None:
    """Atomic write: tmp -> flush -> fsink -> repay."""
    _ensure_dir_for_file(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass
    os.replace(tmp, path)


def _normalize_text(s: str) -> str:
    s = str(s or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.strip()
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


def _normalize_tags(tags: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    if tags:
        for t in tags:
            t2 = str(t).strip()
            if t2:
                out.append(t2)
    # determinism (important for dedup key)
    return sorted(set(out))


def _dedupe_key(text: str, tags: List[str], kind: str) -> str:
    base = (kind or "").strip().lower() + "\n" + _normalize_text(text) + "\n" + "\n".join(tags)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _tokenize(s: str) -> List[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(s or "")]


def _overlap_score(qt: List[str], dt: List[str]) -> float:
    """Simple scoring: intersection of tokens / skrt(|K|*|D|)."""
    if not qt or not dt:
        return 0.0
    qs = set(qt)
    ds = set(dt)
    inter = len(qs.intersection(ds))
    if inter <= 0:
        return 0.0
    return inter / ((len(qs) * len(ds)) ** 0.5)


class StructuredMemory:
    def __init__(
        self,
        path: Optional[str] = None,
        autosave_interval_sec: float = 2.0,
        dedupe_window_sec: int = 60,
        max_recent_index: int = 5000,
    ) -> None:
        self.path = str(path or _default_structured_path())
        self.autosave_interval_sec = float(autosave_interval_sec)
        self.dedupe_window_sec = int(dedupe_window_sec)
        self.max_recent_index = int(max_recent_index)

        self._lock = threading.RLock()
        self._last_save_ts = 0.0

        self.data: Dict[str, Any] = {"records": [], "alias_map": {}}

        # key -> (id, mtime)
        self._recent: Dict[str, Tuple[str, int]] = {}

        self._load()

    # ---------- I/O ----------

    def _load(self) -> None:
        with self._lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, dict):
                        self.data = raw
                except Exception:
                    self.data = {"records": [], "alias_map": {}}

            if not isinstance(self.data, dict):
                self.data = {"records": [], "alias_map": {}}
            if not isinstance(self.data.get("records"), list):
                self.data["records"] = []
            if not isinstance(self.data.get("alias_map"), dict):
                self.data["alias_map"] = {}

            clean: List[Dict[str, Any]] = []
            for r in self.data["records"]:
                if not isinstance(r, dict):
                    continue
                rid = str(r.get("id") or "").strip()
                if not rid:
                    continue
                txt = _normalize_text(r.get("text") or "")
                tags2 = _normalize_tags(r.get("tags") or [])
                kind = str(r.get("kind") or "").strip()
                try:
                    w = float(r.get("weight", 0.5))
                except Exception:
                    w = 0.5
                w = max(0.0, min(1.0, w))
                try:
                    mt = int(r.get("mtime") or r.get("ts") or _now_ts())
                except Exception:
                    mt = _now_ts()

                rr = dict(r)
                rr["id"] = rid
                rr["text"] = txt
                rr["tags"] = tags2
                rr["kind"] = kind
                rr["weight"] = w
                rr["mtime"] = mt
                clean.append(rr)

            self.data["records"] = clean
            self._rebuild_recent_index_locked()

    def _rebuild_recent_index_locked(self) -> None:
        self._recent.clear()
        recs = self.data.get("records", [])
        tail = recs[-self.max_recent_index :] if len(recs) > self.max_recent_index else recs
        for r in tail:
            try:
                key = _dedupe_key(r.get("text", ""), r.get("tags", []), r.get("kind", ""))
                self._recent[key] = (str(r.get("id")), int(r.get("mtime", 0)))
            except Exception:
                continue

    def _maybe_save(self, force: bool = False) -> None:
        now = time.time()
        if (not force) and (now - self._last_save_ts) < self.autosave_interval_sec:
            return
        with self._lock:
            _atomic_write_json(self.path, self.data)
            self._last_save_ts = time.time()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._maybe_save(force=True)
        return {"ok": True, "path": self.path}

    # ---------- helpers ----------

    def resolve_id(self, doc_id: str, max_hops: int = 8) -> str:
        cur = str(doc_id or "").strip()
        if not cur:
            return ""
        with self._lock:
            amap = self.data.get("alias_map", {}) or {}
            for _ in range(max_hops):
                nxt = amap.get(cur)
                if not nxt or nxt == cur:
                    break
                cur = str(nxt)
        return cur

    def get_record(self, doc_id: str) -> Optional[Dict[str, Any]]:
        rid = self.resolve_id(doc_id)
        if not rid:
            return None
        with self._lock:
            for r in self.data.get("records", []):
                if str(r.get("id")) == rid:
                    return dict(r)
        return None

    # ---------- API ----------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            recs = list(self.data.get("records", []))
            nalias = len(self.data.get("alias_map", {}))
        kinds: Dict[str, int] = {}
        for r in recs:
            k = str(r.get("kind") or "").strip() or "?"
            kinds[k] = kinds.get(k, 0) + 1
        return {
            "ok": True,
            "records": len(recs),
            "aliases": nalias,
            "kinds": kinds,
            "path": self.path,
            "autosave_interval_sec": self.autosave_interval_sec,
            "dedupe_window_sec": self.dedupe_window_sec,
        }

    def alias(self, doc_id: str, new_id: str) -> Dict[str, Any]:
        """Sovmestimo so starym API: alias(old_id, new_id)."""
        a = str(doc_id or "").strip()
        b = str(new_id or "").strip()
        if not a or not b:
            return {"ok": False, "error": "bad_args"}
        with self._lock:
            self.data.setdefault("alias_map", {})[a] = b
            self._maybe_save(force=False)
        return {"ok": True, "from": a, "to": b}

    def forget(self, doc_id: str, force_save: bool = False) -> bool:
        rid = self.resolve_id(doc_id)
        if not rid:
            return False
        with self._lock:
            recs = self.data.get("records", [])
            before = len(recs)
            recs2 = [r for r in recs if str(r.get("id")) != rid]
            if len(recs2) == before:
                return False
            self.data["records"] = recs2

            # remove aliases pointing to the read
            amap = self.data.get("alias_map", {}) or {}
            if isinstance(amap, dict):
                dead = [k for k, v in amap.items() if str(v) == rid]
                for k in dead:
                    try:
                        del amap[k]
                    except Exception:
                        pass

            self._rebuild_recent_index_locked()
            self._maybe_save(force=force_save)
            return True

    def add_record(
        self,
        text: str,
        tags: Optional[List[str]] = None,
        weight: float = 0.5,
        kind: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        rid: Optional[str] = None,
        dedupe: bool = True,
        force_save: bool = False,
    ) -> str:
        """Sovmestimo so starym API: add_record(text, tags=None, weight=0.5)
        Expansion: kind=..., meta=..., dedupe=..., force_save=...

        dedupe=True:
        - esli v poslednie dedupe_window_sec uzhe byla exactly takaya zhe zapis (text+tags+kind),
          vernet suschestvuyuschiy id i ne sozdast dubl."""
        txt = _normalize_text(text)
        tags2 = _normalize_tags(tags)
        knd = (str(kind).strip() if kind is not None else "")
        try:
            w = float(weight)
        except Exception:
            w = 0.5
        w = max(0.0, min(1.0, w))

        if not rid:
            rid = uuid.uuid4().hex

        mt = _now_ts()
        key = _dedupe_key(txt, tags2, knd)

        with self._lock:
            if dedupe:
                prev = self._recent.get(key)
                if prev:
                    prev_id, prev_mt = prev
                    if (mt - int(prev_mt)) <= self.dedupe_window_sec:
                        return str(prev_id)

            rec: Dict[str, Any] = {
                "id": str(rid),
                "text": txt,
                "tags": tags2,
                "kind": knd,
                "weight": w,
                "mtime": mt,
            }
            if isinstance(meta, dict) and meta:
                rec["meta"] = meta

            self.data.setdefault("records", []).append(rec)

            self._recent[key] = (str(rid), mt)
            if len(self._recent) > (self.max_recent_index * 2):
                self._rebuild_recent_index_locked()

            self._maybe_save(force=force_save)
            return str(rid)

    def flashback(
        self,
        query: str,
        k: int = 5,
        top_k: Optional[int] = None,
        kind: Optional[str] = None,
        tags_any: Optional[List[str]] = None,
        tags_all: Optional[List[str]] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search by memory.
        top_k - alias for k."""
        if top_k is not None:
            k = top_k
        k = max(1, int(k))

        q = _normalize_text(query)
        qt = _tokenize(q)

        kind_filter = (str(kind).strip() if kind is not None else "")
        any_tags = set(_normalize_tags(tags_any))
        all_tags = set(_normalize_tags(tags_all))

        out: List[Dict[str, Any]] = []
        with self._lock:
            recs = list(self.data.get("records", []))

        now = _now_ts()

        for r in recs:
            txt = str(r.get("text") or "")
            if not txt:
                continue

            rk = str(r.get("kind") or "").strip()
            if kind_filter and rk != kind_filter:
                continue

            rt = set(r.get("tags") or [])
            if any_tags and rt.isdisjoint(any_tags):
                continue
            if all_tags and not all_tags.issubset(rt):
                continue

            dt = _tokenize(txt)
            base = _overlap_score(qt, dt)

            # legkiy bonus za podstroku
            if q and q.lower() in txt.lower():
                base += 0.05

            try:
                w = float(r.get("weight", 0.5))
            except Exception:
                w = 0.5
            w = max(0.0, min(1.0, w))

            # very soft age decay (does not kill old recordings)
            try:
                mt = int(r.get("mtime") or 0)
            except Exception:
                mt = 0
            age = max(1, now - mt)
            decay = 1.0 / (1.0 + (age / (3600 * 24 * 30)))  # ~month as a unit of scale

            score = base * (0.6 + 0.4 * w) * decay
            if score < float(min_score):
                continue

            out.append(
                {
                    "id": str(r.get("id")),
                    "text": txt,
                    "tags": list(r.get("tags") or []),
                    "kind": rk,
                    "weight": w,
                    "score": float(score),
                    "mtime": mt,
                }
            )

        out.sort(key=lambda x: (x["score"], x["mtime"]), reverse=True)
        return out[:k]

    def compact(
        self,
        dry_run: bool = True,
        merge_duplicates: bool = True,
        keep: str = "newest",
        force_save: bool = True,
    ) -> Dict[str, Any]:
        """Ubiraet pustye zapisi, optsionalno slivaet dubli.

        merge_duplicates=True:
        - dubl schitaetsya po (normalized_text + kind)
        keep: newest|oldest — kakuyu zapis ostavit kak “nositel id”"""
        keep = (keep or "newest").strip().lower()
        if keep not in ("newest", "oldest"):
            keep = "newest"

        with self._lock:
            recs = list(self.data.get("records", []))

        deleted = 0
        merged = 0

        # 1) remove void + normalize
        filtered: List[Dict[str, Any]] = []
        for r in recs:
            txt = _normalize_text(r.get("text") or "")
            if not txt:
                deleted += 1
                continue
            rr = dict(r)
            rr["text"] = txt
            rr["tags"] = _normalize_tags(rr.get("tags") or [])
            rr["kind"] = str(rr.get("kind") or "").strip()
            try:
                rr["weight"] = float(rr.get("weight", 0.5))
            except Exception:
                rr["weight"] = 0.5
            rr["weight"] = max(0.0, min(1.0, float(rr["weight"])))
            try:
                rr["mtime"] = int(rr.get("mtime") or _now_ts())
            except Exception:
                rr["mtime"] = _now_ts()
            filtered.append(rr)

        # 2) slit dubli
        if merge_duplicates:
            buckets: Dict[str, List[Dict[str, Any]]] = {}
            for r in filtered:
                key = (str(r.get("kind") or "").strip().lower() + "\n" + _normalize_text(r.get("text") or "")).strip()
                buckets.setdefault(key, []).append(r)

            merged_list: List[Dict[str, Any]] = []
            for _, items in buckets.items():
                if len(items) == 1:
                    merged_list.append(items[0])
                    continue

                items_sorted = sorted(items, key=lambda x: int(x.get("mtime", 0)))
                keeper = items_sorted[-1] if keep == "newest" else items_sorted[0]
                others = [x for x in items if x is not keeper]

                tagset = set(keeper.get("tags") or [])
                wmax = float(keeper.get("weight", 0.5))
                for o in others:
                    for t in (o.get("tags") or []):
                        tagset.add(str(t))
                    try:
                        wmax = max(wmax, float(o.get("weight", 0.5)))
                    except Exception:
                        pass

                keeper["tags"] = sorted(tagset)
                keeper["weight"] = max(0.0, min(1.0, wmax))

                merged += (len(items) - 1)
                merged_list.append(keeper)

            filtered = merged_list

        report = {"deleted": deleted, "merged": merged, "dry_run": bool(dry_run)}

        if dry_run:
            return report

        with self._lock:
            self.data["records"] = filtered

            # clean up alias_map: leave only valid ones
            ids = {str(r.get("id")) for r in filtered}
            amap = self.data.get("alias_map", {}) or {}
            if isinstance(amap, dict):
                dead = [k for k, v in amap.items() if str(v) not in ids]
                for k in dead:
                    try:
                        del amap[k]
                    except Exception:
                        pass

            self._rebuild_recent_index_locked()
            self._maybe_save(force=force_save)

        return {"deleted": deleted, "merged": merged, "dry_run": False}


# ---- SLI (optional, convenient for debugging) ----

def _cli() -> int:
    ap = argparse.ArgumentParser(description="StructuredMemory tool")
    ap.add_argument("--path", default=r".\data\memory\structured.json")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("stats")

    p_add = sub.add_parser("add")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--kind", default="")
    p_add.add_argument("--tags", default="")
    p_add.add_argument("--weight", type=float, default=0.5)

    p_fb = sub.add_parser("flashback")
    p_fb.add_argument("--q", required=True)
    p_fb.add_argument("--k", type=int, default=5)

    p_cp = sub.add_parser("compact")
    p_cp.add_argument("--apply", action="store_true")
    p_cp.add_argument("--merge", action="store_true")
    p_cp.add_argument("--keep", default="newest")

    args = ap.parse_args()
    m = StructuredMemory(args.path)

    if args.cmd == "stats":
        print(json.dumps(m.stats(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "add":
        tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
        rid = m.add_record(args.text, tags=tags, kind=(args.kind or "").strip(), weight=float(args.weight))
        print(rid)
        return 0

    if args.cmd == "flashback":
        res = m.flashback(args.q, top_k=int(args.k))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "compact":
        res = m.compact(dry_run=(not args.apply), merge_duplicates=bool(args.merge), keep=args.keep)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())