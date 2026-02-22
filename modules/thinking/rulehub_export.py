# -*- coding: utf-8 -*-
"""
modules/thinking/rulehub_export.py — chtenie zhurnala RuleHub i eksport v NDJSON/CSV.

Funktsii:
  - read_last(limit=100, status=None) -> List[dict]
  - to_ndjson(rows: List[dict]) -> str
  - to_csv(rows: List[dict]) -> str

Mosty:
- Yavnyy: (Nablyudaemost ↔ Ekspluatatsiya) edinyy modul eksporta dlya UI/REST i CI.
- Skrytyy #1: (Infoteoriya ↔ Kachestvo) unifitsirovannye polya zhurnala uproschayut posleduyuschiy analiz.
- Skrytyy #2: (Kibernetika ↔ Regulyatsiya) filtr po statusu pozvolyaet bystro otsenivat «uzkie mesta».

Zemnoy abzats:
Eto «semschik pokazaniy» s takhografa: beret poslednie zapisi, upakovyvaet v potok (NDJSON) ili tablitsu (CSV) — bez lishnikh zavisimostey.

# c=a+b
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_STATE_DIR = Path(os.getcwd()) / "data" / "rulehub"
_LOG = _STATE_DIR / "log.jsonl"

def _ensure():
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not _LOG.exists():
        _LOG.write_text("", encoding="utf-8")

def read_last(limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Vozvraschaet poslednie limit sobytiy zhurnala s optsionalnym filtrom status ('ok'|'err'|'blocked').
    """
    _ensure()
    rows: List[Dict[str, Any]] = []
    try:
        lines = _LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        lines = []
    for s in lines[-max(1, limit):]:
        try:
            j = json.loads(s)
        except Exception:
            continue
        if status and str(j.get("status")) != status:
            continue
        rows.append(j)
    return rows

def to_ndjson(rows: List[Dict[str, Any]]) -> str:
    """
    Preobrazuet spisok sobytiy v NDJSON-stroki.
    """
    buf = io.StringIO()
    for r in rows:
        buf.write(json.dumps(r, ensure_ascii=False) + "\n")
    return buf.getvalue()

def to_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Preobrazuet spisok sobytiy v CSV (utf-8). Kolonki: ts, status, actions, duration_ms, input_len, blocked, error, result_hint.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ts", "status", "actions", "duration_ms", "input_len", "blocked", "error", "result_hint"])
    for r in rows:
        w.writerow([
            r.get("ts", ""),
            r.get("status", ""),
            ", ".join(r.get("actions", []) or []),
            r.get("duration_ms", 0),
            r.get("input_len", 0),
            ", ".join(r.get("blocked", []) or []),
            (r.get("error") or "")[:500],
            (r.get("result_hint") or "")[:500],
        ])
# return buf.getvalue()