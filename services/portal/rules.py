# -*- coding: utf-8 -*-
"""R6/services/portal/rules.py - primenenie pravil k daydzhestu: filtry, limity, anti-ekho, diversifikatsiya.

Mosty:
- Yavnyy: Enderton — pravila kak proveryaemye predikaty nad (user, tags, text), kompozitsiya daet determinirovannuyu vydachu.
- Skrytyy #1: Cover & Thomas — umenshaem entropiyu (povtory) i povyshaem raznoobrazie (MMR).
- Skrytyy #2: Ashbi — A/B-slot: B vklyuchaet MMR i obschiy anti-ekho mezhdu sektsiyami; sboy ⇒ katbek v A.

Zemnoy abzats (inzheneriya):
Zagruzhaem JSON-pravila, k kazhdomu razdelu primenyaem: allow/deny po tegam/polzovatelyam, regex-blokirovki,
dedup, limity per_tag/per_user, zatem (opts.) MMR i usechenie top_per_section. All na stdlib.

# c=a+b"""
from __future__ import annotations
import json
import os
import re
from typing import Dict, List, Tuple

from services.portal.diversity import dedup_items, jaccard, mmr_select  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _as_set(v) -> set:
    if not v:
        return set()
    if isinstance(v, list):
        return {str(x) for x in v}
    return {str(v)}

def _compile_regexes(patterns: List[str]) -> List[re.Pattern]:
    out = []
    for p in patterns or []:
        try:
            out.append(re.compile(p))
        except Exception:
            continue
    return out

def _blocked(text: str, regs: List[re.Pattern]) -> bool:
    return any(r.search(text or "") for r in regs)

def _apply_filters(items: List[dict], allow_tags: set, deny_tags: set, allow_users: set, deny_users: set, regs: List[re.Pattern]) -> List[dict]:
    out = []
    for it in items:
        tags = set(it.get("tags") or [])
        usr = str(it.get("user") or "")
        text = (it.get("summary") or "") + " " + (it.get("snippet") or "")
        if deny_users and usr in deny_users:
            continue
        if allow_users and usr not in allow_users:
            continue
        if deny_tags and tags & deny_tags:
            continue
        if allow_tags and not (tags & allow_tags):
            continue
        if regs and _blocked(text, regs):
            continue
        out.append(it)
    return out

def _enforce_caps(items: List[dict], per_tag: Dict[str, int], per_user: Dict[str, int]) -> List[dict]:
    tag_cnt: Dict[str, int] = {}
    user_cnt: Dict[str, int] = {}
    out = []
    for it in items:
        usr = str(it.get("user") or "")
        tags = list(it.get("tags") or [])
        # Let's check the limits: if at least one tag is exceeded, we skip it
        skip = False
        for t in tags:
            cap = int(per_tag.get(t, 1_000_000))
            if tag_cnt.get(t, 0) >= cap:
                skip = True
                break
        if not skip:
            capu = int(per_user.get(usr, 1_000_000))
            if user_cnt.get(usr, 0) >= capu:
                skip = True
        if skip:
            continue
        # uchet
        for t in tags:
            tag_cnt[t] = tag_cnt.get(t, 0) + 1
        user_cnt[usr] = user_cnt.get(usr, 0) + 1
        out.append(it)
    return out

def apply_rules_to_digest(digest: Dict, rules: Dict) -> Tuple[Dict, Dict]:
    """
    Vozvraschaet (novyy_digest, statistika).
    """
    mode = (os.getenv("R6_MODE") or "A").strip().upper()
    dedup_thresh = float(os.getenv("R6_DEDUP_THRESH") or rules.get("dedup_threshold") or 0.82)
    lam = float(os.getenv("R6_MMR_LAMBDA") or (rules.get("mmr", {}).get("lambda", 0.7)))

    allow_tags = _as_set(rules.get("allow_tags"))
    deny_tags = _as_set(rules.get("deny_tags"))
    allow_users = _as_set(rules.get("allow_users"))
    deny_users = _as_set(rules.get("deny_users"))
    regs = _compile_regexes(list(rules.get("regex_block") or []))

    per_tag = {str(k): int(v) for k, v in (rules.get("per_tag_max") or {}).items()}
    per_user = {str(k): int(v) for k, v in (rules.get("per_user_max") or {}).items()}
    top_per = int(rules.get("top_per_section") or 0)
    cross = bool((rules.get("cross_section_dedup") or False) if mode == "B" else False)

    stats = {"sections": 0, "before": 0, "after": 0, "removed_dup": 0, "removed_block": 0}
    new = dict(digest)
    new["mode"] = new.get("mode") or "A"
    new["meta"] = dict(new.get("meta") or {})
    new["meta"]["r6_applied"] = True
    new["meta"]["r6_mode"] = mode
    new_sections: List[Dict] = []

    global_texts: List[str] = []

    for s in (digest.get("sections") or []):
        stats["sections"] += 1
        items = list(s.get("items") or [])
        stats["before"] += len(items)

        # 1) Filtry allow/deny i regex
        filtered = _apply_filters(items, allow_tags, deny_tags, allow_users, deny_users, regs)

        # 2) Dedup vnutri sektsii
        deduped = dedup_items(filtered, threshold=dedup_thresh)

        # 3) MMR (v B-rezhime)
        final_items = deduped
        if mode == "B" and (rules.get("mmr", {}).get("enabled", True)):
            try:
                final_items = mmr_select(s.get("query") or "", deduped, k=(top_per or len(deduped)), lam=lam)
            except Exception:
                final_items = deduped  # katbek

        # 4) Limity po tegam/polzovatelyam
        final_items = _enforce_caps(final_items, per_tag, per_user)

        # 5) Usechenie top_per_section
        if top_per and len(final_items) > top_per:
            final_items = final_items[:top_per]

        # 6) Intersectional anti-echo (only in B)
        if mode == "B" and cross:
            keep: List[dict] = []
            for it in final_items:
                txt = (it.get("summary") or "") + " " + (it.get("snippet") or "")
                if any(jaccard(txt, prev) >= dedup_thresh for prev in global_texts):
                    continue
                keep.append(it)
                global_texts.append(txt)
            final_items = keep

        stats["after"] += len(final_items)
        stats["removed_dup"] = max(0, stats["before"] - stats["after"])  # priblizhenno
        new_sections.append({
            "query": s.get("query"),
            "tags": s.get("tags") or [],
            "top": s.get("top") or 0,
            "items": final_items
        })

    new["sections"] = new_sections
    return new, stats
# c=a+b