# -*- coding: utf-8 -*-
"""
R5/services/portal/digest_builder.py — yadro sborki daydzhesta (zakrytaya korobka, offlayn).

Mosty:
- Yavnyy: Enderton (logika) — daydzhest kak kompozitsiya proveryaemykh predikatov: {est kandidaty} ∧ {validnaya struktura} ∧ {determinirovannaya zapis}.
- Skrytyy #1: Cover & Thomas (infoteoriya) — szhimaem signal v korotkie summary (R4) i strukturiruem v JSON/MD (minimum shuma).
- Skrytyy #2: Ashbi (kibernetika) — A/B-slot R5_MODE: B dobavlyaet gruppirovku/annotatsii; pri sboe — avtokatbek v A.

Zemnoy abzats (inzheneriya):
Berem zaprosy/tegi iz plana, vyzyvaem R4 B-slot (s avtokatbekom v A-slot TF-IDF), formiruem
edinyy JSON i Markdown. Nikakoy seti, tolko stdlib. Fayly kladem v PERSIST_DIR/portal/digests/.

# c=a+b
"""
from __future__ import annotations
import datetime as dt
import json
import os
from typing import Any, Dict, List, Tuple

from services.reco.bslot_rerank import bslot_rerank  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _paths() -> Tuple[str, str, str]:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    portal = os.path.join(base, "portal")
    dig = os.path.join(portal, "digests")
    os.makedirs(dig, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return dig, os.path.join(dig, f"digest_{ts}.json"), os.path.join(dig, f"digest_{ts}.md")

def _ensure_list(x) -> List[str]:
    if not x:
        return []
    if isinstance(x, list):
        return [str(i) for i in x]
    if isinstance(x, str):
        return [s.strip() for s in x.split(",") if s.strip()]
    return []

def _section(query: str, tags: List[str], top: int) -> Dict[str, Any]:
    res = bslot_rerank(query, top=top, tags=tags or None)
    items = []
    for r in res:
        meta = r.get("meta") or {}
        items.append({
            "summary": r.get("summary") or meta.get("snippet") or "",
            "score_a": float(r.get("score_a", 0.0)),
            "score_b": float(r.get("score_b", r.get("score_a", 0.0))),
            "user": meta.get("user", "unknown"),
            "tags": meta.get("tags") or [],
            "ts": meta.get("ts") or 0,
            "snippet": meta.get("snippet") or ""
        })
    return {"query": query, "tags": tags, "top": top, "items": items}

def build_digest(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    plan = {
      "title": "Startovyy daydzhest",
      "sections": [
        {"query": "Ester ingenst", "tags": ["rss","inbox"], "top": 5},
        {"query": "demo opisanie", "top": 5}
      ]
    }
    """
    title = (plan.get("title") or "Ester Digest").strip()
    sections_cfg = plan.get("sections") or []
    mode = (os.getenv("R5_MODE") or "A").strip().upper()

    sections: List[Dict[str, Any]] = []
    for sc in sections_cfg:
        q = (sc or {}).get("query", "").strip()
        if not q:
            continue
        tags = _ensure_list((sc or {}).get("tags") or [])
        top = int((sc or {}).get("top") or 5)
        sections.append(_section(q, tags, top))

    digest: Dict[str, Any] = {
        "title": title,
        "generated_utc": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "mode": "B" if mode == "B" else "A",
        "sections": sections,
        "meta": {"engine": "R5", "version": 1}
    }

    if mode == "B":
        try:
            # Gruppirovka po tegam dlya vizualnykh «lentochek»
            tag_hist: Dict[str, int] = {}
            for s in sections:
                for it in s.get("items", []):
                    for t in (it.get("tags") or []):
                        tag_hist[t] = tag_hist.get(t, 0) + 1
            digest["meta"]["tag_hist"] = tag_hist  # type: ignore[index]
        except Exception:
            digest["mode"] = "A"  # avtokatbek

    return digest

def write_digest_files(digest: Dict[str, Any]) -> Dict[str, str]:
    dig_dir, p_json, p_md = _paths()
    with open(p_json, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)

    # Markdown
    lines: List[str] = []
    lines.append(f"# {digest.get('title')}\n")
    lines.append(f"_UTC: {digest.get('generated_utc')}, mode={digest.get('mode')}_\n")
    if "tag_hist" in (digest.get("meta") or {}):
        lines.append("## Tags\n")
        for t, c in sorted((digest["meta"]["tag_hist"] or {}).items()):  # type: ignore[index]
            lines.append(f"- `{t}`: {c}")
        lines.append("")
    for s in digest.get("sections", []):
        lines.append(f"## {s.get('query')}  {' '.join('`#'+t for t in (s.get('tags') or []))}")
        for i, it in enumerate(s.get("items", []), 1):
            lines.append(f"{i}. {it.get('summary')}  — _tags: {', '.join(it.get('tags') or [])}_")
        lines.append("")
    with open(p_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"json": p_json, "md": p_md, "dir": dig_dir}