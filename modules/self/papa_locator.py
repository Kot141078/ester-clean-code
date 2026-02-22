# -*- coding: utf-8 -*-
"""
Owner profile locator.

Builds search patterns from Web UI identity profile and performs best-effort
lookup in local memory, with optional lightweight P2P lookup.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from modules.state.identity_store import load_profile

SEARCH_AB = (os.getenv("PAPA_SEARCH_AB", "A") or "A").upper()
SCOPE = os.getenv("PAPA_SEARCH_SCOPE", "local")


def _norm(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return value


def _patterns() -> List[str]:
    profile = load_profile()
    base = ["owner", "guardian"]
    aliases = [x.strip() for x in str(profile.get("owner_aliases") or "").split(",") if x.strip()]
    for key in ("human_name", "owner_birth_date", "owner_personal_code", "owner_birth_place"):
        value = str(profile.get(key) or "").strip()
        if value:
            base.append(value)
    base.extend(aliases)

    out: List[str] = []
    for token in base:
        norm = _norm(token)
        if norm and norm not in out:
            out.append(norm)
    return out


def search_local(q: str | None = None, k: int = 50) -> Dict[str, Any]:
    if SEARCH_AB == "B":
        return {"ok": True, "items": []}

    tokens = set(_norm(q).split()) if q else set(_patterns())
    items: List[Dict[str, Any]] = []
    try:
        from services.mm_access import get_mm  # type: ignore

        mm = get_mm()
        search = getattr(mm, "search", None) or getattr(mm, "find", None)
        if search:
            query = " ".join(sorted(tokens)) or "owner profile"
            res = search(q=query, k=k) or {}
            items = (res.get("items") or [])[:k]
    except Exception:
        pass
    return {"ok": True, "items": items, "tokens": sorted(tokens)}


def search_p2p(q: str | None = None, k: int = 10, timeout: float = 4.0) -> Dict[str, Any]:
    if SEARCH_AB == "B" or SCOPE != "p2p":
        return {"ok": True, "items": [], "scope": "disabled"}

    peers_path = os.getenv("P2P_KNOWN_PEERS_PATH", "data/peers/known.json")
    try:
        peers = json.load(open(peers_path, "r", encoding="utf-8"))
    except Exception:
        peers = []

    hits: List[Dict[str, Any]] = []
    if not peers:
        return {"ok": True, "items": hits, "peers": 0}

    import requests

    tokens = sorted(list(set(_norm(q).split())) if q else _patterns())
    for peer in peers[:8]:
        url = str(peer.get("url") or "").rstrip("/")
        if not url:
            continue
        try:
            resp = requests.post(
                url + "/p2p/search",
                json={"tokens": tokens, "kind": "owner:profile", "k": k},
                timeout=timeout,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            for item in (data.get("items") or [])[:k]:
                hits.append({"peer": url, "item": item})
        except Exception:
            continue
    return {"ok": True, "items": hits, "peers": len(peers)}
