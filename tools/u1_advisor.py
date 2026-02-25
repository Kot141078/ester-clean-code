#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U1/tools/u1_advisor.py - sovetnik/orkestrator: iz “zabot” → daydzhest → pravila → portal → sovet.

Mosty:
- Yavnyy: Enderton — lineynaya kompozitsiya predikatov: temy → plan → daydzhest → pravila → HTML/advice.
- Skrytyy #1: Ashbi — regulyator prosche: odnoprokhodnyy stsenariy, bez fonovykh demonov, myagkie otkazy.
- Skrytyy #2: Cover & Thomas — minimalnye, no informativnye artefakty: JSON/MD/HTML i advice.md.

Zemnoy abzats (inzheneriya):
Chitaet kontekst zabot iz fayla/STDIN ili iz pamyati, izvlekaet temy, optsionalno triggerit ingenst po konfigu,
construction indexes, sobiraet daydzhest (R5), primenyaet pravila (R6), renderit portal, pishet council (advice.md).
B-rezhim dopolnitelno formiruet blok “Rekomendatsii” i sokhranyaet ego v outbox/telegram_advice.txt (bez otpravki).

# c=a+b"""
from __future__ import annotations
import argparse, json, os, sys
from typing import Dict, Any, List

from services.advisor.topic_extractor import extract_topics  # type: ignore
from services.advisor.planner import build_plan_from_topics  # type: ignore

# Р2/Рз/Р5/Рб - we use their public functions
from services.reco.scorer_a import reco_build  # type: ignore
from services.portal.digest_builder import build_digest, write_digest_files  # type: ignore
from services.portal.rules import apply_rules_to_digest  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _read_text(path: str | None) -> str:
    if path:
        try:
            return open(path, "r", encoding="utf-8").read()
        except Exception:
            return ""
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read()
        except Exception:
            return ""
    return ""

def _maybe_trigger_ingest(cfg_path: str | None) -> None:
    if not cfg_path:
        return
    try:
        # Import and run directly
        from tools.r2_trigger import _load_config as load_cfg  # type: ignore
        from tools.r2_trigger import main as _  # type: ignore
        from services.ingest.rss_ingestor import ingest_rss  # type: ignore
        from services.ingest.file_ingestor import inbox_scan  # type: ignore
        cfg = load_cfg(cfg_path)
        user = os.getenv("ESTER_USER","Owner")
        for it in cfg.get("rss", []):
            url = (it or {}).get("url","")
            tag = (it or {}).get("tag","rss")
            if url:
                ingest_rss(url, user=user, tag=tag)
        for ib in cfg.get("inbox", []):
            path = (ib or {}).get("path","")
            tag = (ib or {}).get("tag","inbox")
            patt = (ib or {}).get("pattern","*.txt;*.md;*.markdown;*.html;*.htm")
            if path:
                inbox_scan(root=path, user=user, tag=tag, pattern=patt)
    except Exception:
        pass  # myagko

def _write_advice(md_path: str, topics: List[str], digest: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Sovet po vashim zabotam\n")
    if topics:
        lines.append("**Vyyavlennye temy:** " + ", ".join(f"`{t}`" for t in topics) + "\n")
    for s in digest.get("sections", []):
        lines.append(f"## {s.get('query')}")
        items = s.get("items") or []
        take = min(5, len(items))
        for i, it in enumerate(items[:take], 1):
            lines.append(f"{i}. {it.get('summary')}  — _tags: {', '.join(it.get('tags') or [])}_")
        lines.append("")
    # easy recommendations in B-mode
    if (os.getenv("U1_MODE") or "A").strip().upper() == "B":
        try:
            lines.append("## Rekomendatsii\n")
            lines.append("- Sign/update RCC sources close to the topics above (edits in ёУ1_ИНГЭСТ_CONFIGIO).")
            lines.append("- Enable eRch_MODE=Byo with local LM Studio for better reranking.")
            lines.append("- Check the report yoobs_report.mdieu on the SLO of key steps (P7).")
        except Exception:
            pass
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def _maybe_outbox_telegram(md_path: str) -> None:
    if (os.getenv("U1_MODE") or "A").strip().upper() != "B":
        return
    if os.getenv("U1_NOTIFY_TELEGRAM","0") != "1":
        return
    # Without a real network: we put a file that can be picked up by an existing processor
    outdir = os.path.join(os.getenv("PERSIST_DIR") or "data", "outbox")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, "telegram_advice.txt")
    try:
        text = open(md_path, "r", encoding="utf-8").read()
        open(outpath, "w", encoding="utf-8").write(text)
    except Exception:
        pass

def main() -> int:
    ap = argparse.ArgumentParser(description="Ester Advisor: concerns → topics → digest → portal")
    ap.add_argument("--context", help="File with a description of concerns (if not specified, read from STDIN and memory)", default=None)
    ap.add_argument("--top", type=int, default=6, help="Maks. chislo tem")
    ap.add_argument("--ingest-config", default=os.getenv("U1_INGEST_CONFIG") or "", help="JSON-konfig ingensta (R2)")
    ap.add_argument("--rules", default=os.getenv("U1_RULES") or "", help="JSON-pravila (R6)")
    args = ap.parse_args()

    # 0) Izvlech temy
    ctx = _read_text(args.context)
    topics = extract_topics(ctx, top=args.top)

    # 1) (optional) ingenst trigger - pull up recent records
    _maybe_trigger_ingest(args.ingest_config if args.ingest_config else None)

    # 2) Indeks
    reco_build()

    # 3) Plan → daydzhest
    plan = build_plan_from_topics(topics or ["vazhnye voprosy"], top_per_section=5)
    digest = build_digest(plan)

    # 4) Pravila
    if args.rules and os.path.isfile(args.rules):
        import json as _json
        rules = _json.load(open(args.rules, "r", encoding="utf-8"))
        digest, _stats = apply_rules_to_digest(digest, rules)

    # 5) Save JSON/MD i portal
    out = write_digest_files(digest)
    from tools.r5_portal_render import main as _  # leg: F401 (gross dependence excluded)
    # Renderim
    from tools.r5_portal_render import render_html as __unused  # dummy to avoid circular import
    os.system(f"{sys.executable} tools/r5_portal_render.py --out portal/index.html")

    # 6) Sovet
    _write_advice("portal/advice.md", topics, digest)
    _maybe_outbox_telegram("portal/advice.md")

    print(json.dumps({
        "ok": 1,
        "topics": topics,
        "digest_json": out.get("json"),
        "digest_md": out.get("md"),
        "portal_html": "portal/index.html",
        "advice_md": "portal/advice.md"
    }, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())