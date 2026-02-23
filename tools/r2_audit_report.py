#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R2/tools/r2_audit_report.py — generatsiya svodnogo otcheta po audit-logam ingensta.

Mosty:
- Yavnyy: Cover & Thomas — agregiruem metriki (added/seen/errors) dlya umensheniya neopredelennosti statusa.
- Skrytyy #1: Enderton — svodka kak predikaty nad chislami; format otcheta determinirovan i proveryaem.
- Skrytyy #2: Ashbi — regulyator prosche: odnorazovyy prokhod po JSONL, bez tyazheloy analitiki.

Zemnoy abzats (inzheneriya):
Chitaet `PERSIST_DIR/ingest/audit.jsonl` i stroit Markdown s summami za vse vremya i poslednyuyu sessiyu.
Rabotaet tolko na stdlib. Umeet pisat v fayl (`--out`) ili stdout. Bezopasen dlya CI.

# c=a+b
"""
from __future__ import annotations
import argparse
import json
import os
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _paths():
    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    audit_jsonl = os.path.join(persist_dir, "ingest", "audit.jsonl")
    return audit_jsonl

def _read_all(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows

def _agg(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    total = {"rss_added": 0, "rss_errors": 0, "inbox_added": 0, "inbox_skipped": 0}
    last = {"rss_added": 0, "rss_errors": 0, "inbox_added": 0, "inbox_skipped": 0}
    if not rows:
        return total, last

    for r in rows:
        for it in r.get("rss", []):
            res = it.get("res") or {}
            total["rss_added"] += int(res.get("added", 0))
            total["rss_errors"] += int(res.get("errors", 0))
        for it in r.get("inbox", []):
            res = it.get("res") or {}
            total["inbox_added"] += int(res.get("added", 0))
            total["inbox_skipped"] += int(res.get("skipped", 0))

    last_row = rows[-1]
    for it in last_row.get("rss", []):
        res = it.get("res") or {}
        last["rss_added"] += int(res.get("added", 0))
        last["rss_errors"] += int(res.get("errors", 0))
    for it in last_row.get("inbox", []):
        res = it.get("res") or {}
        last["inbox_added"] += int(res.get("added", 0))
        last["inbox_skipped"] += int(res.get("skipped", 0))

    return total, last

def _render_md(rows: List[Dict[str, Any]], total: Dict[str, int], last: Dict[str, int]) -> str:
    lines: List[str] = []
    lines.append("# Ingest audit report\n")
    lines.append("## Totals\n")
    lines.append(f"- RSS: added={total['rss_added']}, errors={total['rss_errors']}")
    lines.append(f"- INBOX: added={total['inbox_added']}, skipped={total['inbox_skipped']}\n")
    lines.append("## Last run\n")
    lines.append(f"- RSS: added={last['rss_added']}, errors={last['rss_errors']}")
    lines.append(f"- INBOX: added={last['inbox_added']}, skipped={last['inbox_skipped']}\n")
    lines.append("## History (last 10)\n")
    for r in rows[-10:]:
        lines.append(f"- {r.get('ts')} — rss={len(r.get('rss',[]))}, inbox={len(r.get('inbox',[]))}")
    lines.append("")
    return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(description="Otchet po audit-logam ingensta (Markdown)")
    ap.add_argument("--out", default="-", help="Fayl vyvoda ili '-' dlya stdout")
    args = ap.parse_args()

    path = _paths()
    rows = _read_all(path)
    total, last = _agg(rows)
    md = _render_md(rows, total, last)

    if args.out != "-":
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"[r2_audit_report] Otchet zapisan v {args.out}")
        except Exception as e:
            print(f"[r2_audit_report] WARN: ne udalos zapisat fayl: {e}")
            print(md)
    else:
        print(md)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
