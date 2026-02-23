#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R2/tools/r2_trigger.py — edinyy trigger ingensta po konfigu (JSON), bezopasnyy dlya cron/planirovschika.

Mosty:
- Yavnyy: Enderton (logika) — konfig kak nabor predikatov nad zadachami (rss|inbox), proveryaemyy bez izmeneniya rantayma.
- Skrytyy #1: Ashbi (kibernetika) — regulyator prosche sistemy: lineynyy zapusk zadach, otsutstvie fonovykh demonov.
- Skrytyy #2: Cover & Thomas (infoteoriya) — audit fiksiruet «signal» (added/seen), snizhaya neopredelennost sostoyaniya pamyati.

Zemnoy abzats (inzheneriya):
Chitaet JSON-konfig so spiskami istochnikov RSS i putyami inbox, vyzyvaet ingenst iz R2/paket-01 i
zapisyvaet audit v `PERSIST_DIR/ingest/audit.jsonl` (po stroke na zapusk) i kratkiy Markdown-log (append).
Tolko stdlib, bez PyYAML — chtoby ne taschit zavisimosti v closed-box.

# c=a+b
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List

from services.ingest.rss_ingestor import ingest_rss  # type: ignore
from services.ingest.file_ingestor import inbox_scan  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _paths():
    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    ingest_dir = os.path.join(persist_dir, "ingest")
    os.makedirs(ingest_dir, exist_ok=True)
    audit_jsonl = os.path.join(ingest_dir, "audit.jsonl")
    audit_md = os.path.join(ingest_dir, "audit.md")
    return audit_jsonl, audit_md

def _load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Normalizuem polya
    cfg.setdefault("rss", [])
    cfg.setdefault("inbox", [])
    return cfg

def _append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _append_md(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)

def main() -> int:
    ap = argparse.ArgumentParser(description="Ester R2 ingest trigger (JSON config)")
    ap.add_argument("--config", required=True, help="Put k JSON-konfigu")
    ap.add_argument("--user", default=os.getenv("ESTER_USER", "Owner"), help="Imya polzovatelya dlya kartochek")
    ap.add_argument("--dry-run", action="store_true", help="Ne zapisyvat audit (tolko pechat)")
    args = ap.parse_args()

    cfg = _load_config(args.config)
    ts = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    audit_jsonl, audit_md = _paths()

    batch_summary: Dict[str, Any] = {
        "ts": ts,
        "user": args.user,
        "rss": [],
        "inbox": [],
    }

    # RSS
    for item in cfg.get("rss", []):
        url = (item or {}).get("url", "")
        tag = (item or {}).get("tag", "rss")
        if not url:
            continue
        res = ingest_rss(url, user=args.user, tag=tag)
        res_entry = {"url": url, "tag": tag, "res": res}
        batch_summary["rss"].append(res_entry)

    # INBOX
    for ib in cfg.get("inbox", []):
        path = (ib or {}).get("path", "")
        tag = (ib or {}).get("tag", "inbox")
        pattern = (ib or {}).get("pattern", "*.txt;*.md;*.markdown;*.html;*.htm")
        if not path:
            continue
        res = inbox_scan(root=path, user=args.user, tag=tag, pattern=pattern)
        res_entry = {"path": path, "tag": tag, "pattern": pattern, "res": res}
        batch_summary["inbox"].append(res_entry)

    # Pechat i audit
    print(json.dumps(batch_summary, ensure_ascii=False, indent=2))

    if not args.dry_run:
        _append_jsonl(audit_jsonl, batch_summary)
        # Kompaktnaya zapis v Markdown
        lines: List[str] = []
        lines.append(f"### {ts}\n")
        for r in batch_summary["rss"]:
            rr = r["res"]
            lines.append(f"- RSS `{r['url']}` tag=`{r['tag']}` ⇒ added={rr.get('added',0)}, seen={rr.get('seen',0)}, ok={rr.get('ok',0)}, errors={rr.get('errors',0)}")
        for r in batch_summary["inbox"]:
            rr = r["res"]
            lines.append(f"- INBOX `{r['path']}` tag=`{r['tag']}` ⇒ added={rr.get('added',0)}, seen={rr.get('seen',0)}, skipped={rr.get('skipped',0)}, ok={rr.get('ok',0)}")
        lines.append("\n")
        _append_md(audit_md, "\n".join(lines))

    return 0

if __name__ == "__main__":
    pass
    # raise SystemExit(main())
