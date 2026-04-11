# -*- coding: utf-8 -*-
"""
modules/memory/store.py — JSON‑память (UI) + стабильная векторизация.

Что показала QA‑диагностика у тебя:
- память забивалась двумя короткими сервисными строками:
  "trace: (цель не определена)" и "think: trace → ok"
  → тысячи дублей = деградация полезного сигнала.

Улучшения v2 (без ломания API):
1) Потокобезопасное сохранение: snapshot пишет копию _MEM (под lock), а не живой dict.
2) Шумовой фильтр + dedupe‑окно:
   - отбрасываем короткие trace/think статусы (настраивается ENV).
   - повтор одного и того же текста в коротком окне (по умолчанию 60с) не засоряет память.
   - запись не падает: возвращается rec с флагом dropped=True.
3) Опциональный capture callsite (чтобы поймать, КТО пишет мусор):
   MEM_CAPTURE_CALLSITE=1 → meta["_src"] = "file.py:line func"
4) Нормальная схема сохраняется как раньше: add_record/get_record/query/forget/snapshot/load.
5) Совместимость с твоими миграциями vec сохранена.

ENV (новые):
- MEM_DEDUP_WINDOW_SEC=60            (0 отключает)
- MEM_DROP_TRACE_THINK=1             (0 отключает)
- MEM_DROP_MAX_LEN=200               (для trace/think фильтра)
- MEM_CAPTURE_CALLSITE=0|1           (по умолчанию 0)
- MEM_SAVE_INTERVAL_SEC=2.0          (как было)

МОСТЫ:
- Явный: QA → фильтр → память перестаёт “самозасоряться”.
- Скрытый #1: инфотеория — защита канала памяти от низкоинформативного повторения.
- Скрытый #2: кибернетика — измерение (QA) приводит к коррекции на входе (store.add_record).
ЗЕМНОЙ АБЗАЦ:
Это как клапан на бойлере: он не делает воду горячее, но не даёт системе взорваться от давления “мусорных” записей.

c=a+b
"""
from __future__ import annotations

import os
import time
import uuid
import threading
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.memory.io import save_snapshot, load_snapshot
from modules.memory.vector import embed, normalize_vec

_LOCK = threading.Lock()
_MEM: Dict[str, Dict[str, Any]] = {}

# --- state root ---
_STATE = (os.environ.get("ESTER_STATE_DIR") or os.environ.get("ESTER_HOME") or "").strip()
if not _STATE:
    _STATE = (os.environ.get("ESTER_ROOT") or os.getcwd()).strip()

_FILE = os.path.join(_STATE, "data", "memory", "memory.json")
os.makedirs(os.path.dirname(_FILE), exist_ok=True)

_SAVE_INTERVAL = float(os.getenv("MEM_SAVE_INTERVAL_SEC", "2.0").strip() or 2.0)
_LAST_SAVE = 0.0

# vec dim policy
_DIM = int(os.getenv("MEM_VEC_DIM", "384").strip() or 384)

# --- noise / dedupe policy ---
_DEDUP_WINDOW = int(os.getenv("MEM_DEDUP_WINDOW_SEC", "60").strip() or 60)  # 0 = off
_DROP_TRACE_THINK = (os.getenv("MEM_DROP_TRACE_THINK", "1").strip() != "0")
_DROP_MAX_LEN = int(os.getenv("MEM_DROP_MAX_LEN", "200").strip() or 200)

_CAPTURE_CALLSITE = (os.getenv("MEM_CAPTURE_CALLSITE", "0").strip() == "1")

# recent hashes -> last_ts (для dedupe окна)
_RECENT: Dict[str, int] = {}
_RECENT_LOCK = threading.Lock()

# Триггеры мусора (минимальный набор, без регулярных выражений по умолчанию)
_NOISE_EXACT = {
    "trace: (цель не определена)",
    "think: trace → ok",
}
_NOISE_PREFIX = ("trace:", "think:")


def _now() -> int:
    return int(time.time())


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _text_hash(norm: str) -> str:
    return hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()


def _parse_ts(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return _now()


def _dedupe_key_for_record(rec: Dict[str, Any]) -> str:
    rid = str(rec.get("id") or "").strip()
    if rid:
        return "id:" + rid

    text = str(rec.get("text") or "")
    ts = str(_parse_ts(rec.get("ts") or rec.get("mtime") or rec.get("time") or 0))
    kind = str(rec.get("type") or rec.get("kind") or "fact")

    meta = rec.get("meta")
    source = ""
    if isinstance(meta, dict):
        source = str(meta.get("source") or "")
    if not source:
        source = str(rec.get("source") or "")

    payload = "\n".join((text, ts, kind, source))
    return "fp:" + hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def _coerce_external_record(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    text = str(raw.get("text") or raw.get("content") or "").strip()
    if not text:
        return None

    ts = _parse_ts(raw.get("ts") or raw.get("mtime") or raw.get("time") or raw.get("timestamp"))
    typ = str(raw.get("type") or raw.get("kind") or raw.get("role") or "fact")

    meta = raw.get("meta")
    meta2: Dict[str, Any] = dict(meta) if isinstance(meta, dict) else {}
    src = str(raw.get("source") or meta2.get("source") or "")
    if src and "source" not in meta2:
        meta2["source"] = src

    rec: Dict[str, Any] = {
        "id": str(raw.get("id") or uuid.uuid4().hex),
        "type": typ,
        "text": text,
        "meta": meta2,
        "ts": ts,
    }
    if "vec" in raw and isinstance(raw.get("vec"), list):
        rec["vec"] = list(raw.get("vec") or [])
    return rec


def _capture_src() -> Optional[str]:
    """
    Очень лёгкий capture callsite без inspect.stack() (он тяжёлый).
    """
    if not _CAPTURE_CALLSITE:
        return None
    try:
        import sys
        # add_record → caller → caller2
        fr = sys._getframe(2)
        fn = fr.f_code.co_filename
        ln = fr.f_lineno
        nm = fr.f_code.co_name
        base = os.path.basename(fn)
        return f"{base}:{ln} {nm}"
    except Exception:
        return None


def _should_drop(text: str) -> Tuple[bool, str]:
    """
    Возвращает (drop, reason).
    """
    t = text or ""
    norm = _norm_text(t)

    if _DROP_TRACE_THINK:
        # точно известные два шаблона
        if norm in _NOISE_EXACT:
            return True, "noise_exact"
        # короткие trace/think статусы (чтобы не убить длинные полезные отчёты)
        if len(norm) <= max(10, _DROP_MAX_LEN) and norm.startswith(_NOISE_PREFIX):
            return True, "noise_prefix"

    # dedupe окно (общая защита от повторов)
    if _DEDUP_WINDOW > 0 and norm:
        h = _text_hash(norm)
        now = _now()
        with _RECENT_LOCK:
            last = _RECENT.get(h)
            if last is not None and (now - int(last)) <= _DEDUP_WINDOW:
                return True, "dedupe_window"
            _RECENT[h] = now

            # мягкая очистка _RECENT
            if len(_RECENT) > 50000:
                cutoff = now - max(1, _DEDUP_WINDOW) * 3
                for k in list(_RECENT.keys())[:2000]:
                    if _RECENT.get(k, 0) < cutoff:
                        _RECENT.pop(k, None)

    return False, ""


def _maybe_save(force: bool = False) -> None:
    """
    Пишем на диск копию _MEM, чтобы не ловить гонки.
    """
    global _LAST_SAVE
    now = time.time()
    if not (force or (now - _LAST_SAVE) >= _SAVE_INTERVAL):
        return

    with _LOCK:
        snap = dict(_MEM)
    save_snapshot(_FILE, snap)
    _LAST_SAVE = now


def _migrate_record_vec(rec: Dict[str, Any]) -> bool:
    """
    Returns True if record changed.
    """
    changed = False
    txt = str(rec.get("text") or "").strip()
    v = rec.get("vec")

    # If vec missing or wrong type/length -> recompute.
    need = False
    if not isinstance(v, list) or not v:
        need = True
    else:
        try:
            if len(v) != _DIM:
                need = True
        except Exception:
            need = True

    if need:
        if isinstance(v, list) and v:
            rec["vec_legacy"] = v
        rec["vec"] = normalize_vec(embed(txt), _DIM)
        changed = True

    # Keep minimal schema sane
    if "id" not in rec:
        rec["id"] = str(uuid.uuid4())
        changed = True
    if "ts" not in rec:
        rec["ts"] = int(time.time())
        changed = True
    if "meta" not in rec or not isinstance(rec.get("meta"), dict):
        rec["meta"] = {}
        changed = True
    if "type" not in rec:
        rec["type"] = "fact"
        changed = True

    return changed


def load() -> None:
    global _MEM
    data = load_snapshot(_FILE) or {}
    if isinstance(data, dict):
        _MEM.update(data)

    # Lazy migration
    changed_any = False
    with _LOCK:
        for k, rec in list(_MEM.items()):
            if isinstance(rec, dict):
                if _migrate_record_vec(rec):
                    changed_any = True
            else:
                _MEM.pop(k, None)
                changed_any = True
    if changed_any:
        _maybe_save(force=True)


def add_record(type_: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Добавляет запись в память.
    Если запись отфильтрована (noise/dedupe), она НЕ пишется в _MEM,
    но возвращается rec с dropped=True, чтобы вызывающий код не падал.
    """
    try:
        from modules.memory.facade import ESTER_MEM_FACADE_STRICT, in_facade, log_violation  # type: ignore
        if ESTER_MEM_FACADE_STRICT and not in_facade():
            log_violation(type_, text, meta or {}, source="modules.memory.store.add_record")
            raise RuntimeError("[MEMORY] direct add_record blocked (use memory_add)")
    except Exception:
        pass
    rid = str(uuid.uuid4())
    now = int(time.time())

    meta2: Dict[str, Any] = dict(meta or {})
    src = _capture_src()
    if src and "_src" not in meta2:
        meta2["_src"] = src

    rec: Dict[str, Any] = {"id": rid, "type": type_ or "fact", "text": text or "", "meta": meta2, "ts": now}

    drop, reason = _should_drop(rec["text"])
    if drop:
        rec["dropped"] = True
        rec["drop_reason"] = reason
        # вектор не считаем для мусора (экономим)
        return rec

    rec["vec"] = normalize_vec(embed(rec["text"]), _DIM)
    with _LOCK:
        _MEM[rid] = rec
    _maybe_save()
    return rec


def get_record(rid: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        return _MEM.get(rid)


def _query_legacy(text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    from modules.memory.vector import search
    if not _MEM:
        return []
    vec = normalize_vec(embed(text), _DIM)
    with _LOCK:
        items = list(_MEM.values())
    return search(vec, items, top_k=top_k)


def query(text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    try:
        from modules.memory.core_sqlite import read_cutover_enabled, search_legacy, shadow_compare, shadow_read_enabled  # type: ignore

        cutover = read_cutover_enabled()
        shadow = shadow_read_enabled()
    except Exception:
        cutover = False
        shadow = False
        search_legacy = None  # type: ignore
        shadow_compare = None  # type: ignore

    legacy_rows: List[Dict[str, Any]] = []

    if cutover and callable(search_legacy):
        try:
            core_rows = search_legacy(text, limit=top_k)  # type: ignore[misc]
            if shadow:
                legacy_rows = _query_legacy(text, top_k=top_k)
                try:
                    if callable(shadow_compare):
                        shadow_compare(text, legacy_rows, core_rows)  # type: ignore[misc]
                except Exception:
                    pass
            return core_rows
        except Exception:
            pass

    legacy_rows = _query_legacy(text, top_k=top_k)

    if shadow and callable(search_legacy):
        try:
            core_rows = search_legacy(text, limit=top_k)  # type: ignore[misc]
            if callable(shadow_compare):
                shadow_compare(text, legacy_rows, core_rows)  # type: ignore[misc]
        except Exception:
            pass

    return legacy_rows


def search(text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    return query(text, top_k=top_k)


def forget(rid: str) -> bool:
    with _LOCK:
        if rid in _MEM:
            del _MEM[rid]
            _maybe_save(force=True)
            return True
    return False


def snapshot() -> None:
    _maybe_save(force=True)


def items() -> List[Dict[str, Any]]:
    with _LOCK:
        return [dict(v) for v in _MEM.values() if isinstance(v, dict)]


def all_items() -> List[Dict[str, Any]]:
    return items()


def ingest_records(records: Iterable[Dict[str, Any]], dedupe: bool = True) -> Dict[str, Any]:
    """
    Ingest records into in-memory store without migrations.
    Dedupes by id (preferred) or sha256(text+ts+kind+source).
    """
    normalized: List[Dict[str, Any]] = []
    for raw in records or []:
        rec = _coerce_external_record(raw)
        if rec is not None:
            normalized.append(rec)

    loaded = 0
    skipped = 0
    inserted_ids: List[str] = []

    with _LOCK:
        existing = set()
        if dedupe:
            for rec in _MEM.values():
                if isinstance(rec, dict):
                    existing.add(_dedupe_key_for_record(rec))

        for rec in normalized:
            dkey = _dedupe_key_for_record(rec)
            if dedupe and dkey in existing:
                skipped += 1
                continue
            rid = str(rec.get("id") or uuid.uuid4().hex)
            rec["id"] = rid
            _MEM[rid] = rec
            loaded += 1
            inserted_ids.append(rid)
            if dedupe:
                existing.add(dkey)

    save_error = ""
    if loaded:
        try:
            _maybe_save(force=False)
        except Exception as e:
            save_error = str(e)

    out = {"ok": True, "loaded": loaded, "skipped": skipped, "total": len(normalized), "ids": inserted_ids}
    if save_error:
        out["save_error"] = save_error
    return out


def load_recent_from_scroll(paths: List[str], max_lines: int = 2000) -> Dict[str, Any]:
    """
    Load recent records from one or more scroll JSONL files.
    """
    try:
        from modules.memory.scroll_reader import read_jsonl_tail  # type: ignore
    except Exception as e:
        return {"ok": False, "error": f"scroll_reader_unavailable: {e}", "loaded": 0, "skipped": 0, "read_lines": 0}

    uniq_paths: List[str] = []
    seen = set()
    for p in paths or []:
        s = str(p or "").strip()
        if not s:
            continue
        try:
            rp = str(Path(s).resolve())
        except Exception:
            rp = s
        if rp in seen:
            continue
        seen.add(rp)
        uniq_paths.append(rp)

    records: List[Dict[str, Any]] = []
    read_lines = 0
    used_paths: List[str] = []

    for p in uniq_paths:
        rows = read_jsonl_tail(p, max_lines=max_lines)
        if not rows:
            continue
        records.extend(rows)
        read_lines += len(rows)
        used_paths.append(p)

    rep = ingest_records(records, dedupe=True)
    rep["paths"] = used_paths
    rep["read_lines"] = read_lines
    return rep


def reset_for_tests(clear_disk: bool = False, file_path: Optional[str] = None) -> None:
    global _FILE
    if file_path:
        _FILE = str(file_path)
        try:
            os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        except Exception:
            pass

    with _LOCK:
        _MEM.clear()
    with _RECENT_LOCK:
        _RECENT.clear()

    if clear_disk:
        try:
            if os.path.exists(_FILE):
                os.remove(_FILE)
        except Exception:
            pass


def stats() -> Dict[str, Any]:
    """
    Мини‑статистика (для UI/диагностики).
    """
    with _LOCK:
        n = len(_MEM)
    return {
        "ok": True,
        "count": n,
        "file": _FILE,
        "save_interval_sec": _SAVE_INTERVAL,
        "dedupe_window_sec": _DEDUP_WINDOW,
        "drop_trace_think": _DROP_TRACE_THINK,
        "capture_callsite": _CAPTURE_CALLSITE,
    }


# автозагрузка при импорте
load()
