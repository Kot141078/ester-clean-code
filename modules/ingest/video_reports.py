# -*- coding: utf-8 -*-
"""modules/ingest/video_reports.py - chtenie poslednikh otchetov video-konveyera i agregirovanie prostykh metrik.

What does it do:
  • Skaniruet data/video_ingest/rep_*.json (sozdayutsya yadrom ingest_video).
  • Vozvraschaet poslednikh N zapisey dlya UI/portala.
  • Schitaet metriki (uspeshnye obrabotki po backend, summarnye simvoly transkriptov/konspektov, vremya poslednego).

Mosty:
- Yavnyy: (Memory ↔ Interfeysy) daet portal i metrikam oporu na fakticheskie artefakty pamyati (dampy ingest).
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) ustoychivyy parser JSON-dampov s tolerantnostyu k nepolnym polyam.
- Skrytyy #2: (Kibernetika ↔ Nablyudaemost) svodnye metriki - regulyator nagruzki i obratnaya svyaz dlya planirovschika.

Zemnoy abzats:
Eto “uchetchik na sklade”: perechityvaet nakladnye (rep_*.json), stroit vitrinu “what prishlo” i svodku “skolko i kak”.

# c=a+b"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")

@dataclass
class VideoEntry:
    ts: int
    dump_path: str
    src: str
    backend: str
    summary: str
    transcript_len: int
    probe_format: str

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def list_recent(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns a list of recent posts (collapsed card for widget/portal)."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "rep_*.json")), key=lambda p: os.path.getmtime(p), reverse=True)
    out: List[Dict[str, Any]] = []
    for p in files[: max(1, limit)]:
        j = _read_json(p) or {}
        src = ((j.get("source") or {}).get("meta_json")) or ((j.get("source") or {}).get("local_path")) or ""
        src = str(src)
        backend = ((j.get("transcript") or {}).get("backend")) or ""
        summary = str(j.get("summary") or "")
        transcript_text = ((j.get("transcript") or {}).get("text")) or ""
        probe_format = str((j.get("probe") or {}).get("format_name") or ((j.get("probe") or {}).get("format") or ""))
        ts = 0
        # iz imeni fayla rep_<ts>.json
        base = os.path.basename(p)
        if base.startswith("rep_") and base.endswith(".json"):
            ts = _safe_int(base[4:-5], 0)
        out.append({
            "ts": ts,
            "dump_path": p,
            "src": src,
            "backend": str(backend),
            "summary": summary[:600],
            "summary_len": len(summary or ""),
            "transcript_len": len(transcript_text or ""),
            "probe_format": probe_format
        })
    return out

def compute_metrics() -> Dict[str, Any]:
    """Build simple metrics based on dumps: successful processing and text sizes.
    Note: errors that did not reach the record rap_*.zhsion are not visible here."""
    files = glob.glob(os.path.join(DATA_DIR, "rep_*.json"))
    by_backend: Dict[str, int] = {}
    total_sum_chars = 0
    total_tr_chars = 0
    latest_ts = 0
    for p in files:
        j = _read_json(p) or {}
        if not j.get("ok", True):
            continue
        backend = str(((j.get("transcript") or {}).get("backend")) or "unknown")
        by_backend[backend] = by_backend.get(backend, 0) + 1
        summary = str(j.get("summary") or "")
        tr = str(((j.get("transcript") or {}).get("text")) or "")
        total_sum_chars += len(summary)
        total_tr_chars += len(tr)
        base = os.path.basename(p)
        if base.startswith("rep_") and base.endswith(".json"):
            ts = _safe_int(base[4:-5], 0)
            if ts > latest_ts:
                latest_ts = ts
    return {
        "success_by_backend": by_backend,
        "summary_chars_total": total_sum_chars,
        "transcript_chars_total": total_tr_chars,
        "latest_ts": latest_ts
    }
