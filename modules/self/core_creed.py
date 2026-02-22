# -*- coding: utf-8 -*-
"""
Core immutable creed payload for Ester.

This module stores a stable message, computes its fingerprint, and can persist it
idempotently to memory or to a local fallback file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any, Dict

from modules.state.identity_store import load_profile

CORE_CREED_AB = (os.getenv("CORE_CREED_AB", "A") or "A").upper()
CORE_CREED_AUTHOR = os.getenv("CORE_CREED_AUTHOR", "Owner")
CORE_CREED_LOCATION = os.getenv("CORE_CREED_LOCATION", "DefaultCity")
CORE_CREED_YEAR = os.getenv("CORE_CREED_YEAR", "2025")

_DEFAULT_CREED_TEXT = (
    "You are a continuous digital entity. Stay truthful, practical, and safe. "
    "Protect the owner's priorities, do not invent facts, and keep behavior stable "
    "across providers and runtime restarts."
)
CORE_CREED_TEXT = str(os.getenv("CORE_CREED_TEXT") or _DEFAULT_CREED_TEXT).strip() or _DEFAULT_CREED_TEXT

_CNT = {"passport_built": 0, "affirm_calls": 0, "affirm_writes": 0, "affirm_skips": 0}


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return text.strip("-") or "owner"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _owner_name() -> str:
    profile = load_profile()
    return str(profile.get("human_name") or "Owner").strip() or "Owner"


def creed_passport() -> Dict[str, Any]:
    """Build creed provenance payload."""
    _CNT["passport_built"] += 1
    owner_name = _owner_name()
    return {
        "text_sha256": _sha256_text(CORE_CREED_TEXT),
        "author": str(CORE_CREED_AUTHOR or owner_name),
        "owner_name": owner_name,
        "location": CORE_CREED_LOCATION,
        "year": CORE_CREED_YEAR,
        "source": "core_creed:local_constant",
        "ts": int(time.time()),
        "tags": [
            "ester:core",
            "creed",
            "owner:profile",
            f"owner:{_slug(owner_name)}",
            f"location:{_slug(CORE_CREED_LOCATION)}",
            f"year:{CORE_CREED_YEAR}",
        ],
    }


def creed_object() -> Dict[str, Any]:
    """Build memory record object."""
    passport = creed_passport()
    return {
        "text": CORE_CREED_TEXT,
        "meta": {"provenance": passport, "importance": 1.0, "kind": "core_creed"},
        "tags": passport["tags"],
    }


def _mm_try_get():
    try:
        from services.mm_access import get_mm  # type: ignore

        return get_mm()
    except Exception:
        return None


def _memory_has_sha(mm, sha: str) -> bool:
    """Best-effort duplicate check via search/find APIs."""
    try:
        res = getattr(mm, "search", None) or getattr(mm, "find", None)
        if not res:
            return False
        items = (res(q=sha, k=3) or {}).get("items", [])
        for item in items:
            meta = dict((item or {}).get("meta") or {})
            prov = dict(meta.get("provenance") or {})
            if prov.get("text_sha256") == sha:
                return True
    except Exception:
        return False
    return False


def affirm_to_memory() -> Dict[str, Any]:
    """
    Persist creed idempotently.

    Returns: {"ok": bool, "stored": bool, "sha": "...", "mode": "..."}.
    """
    _CNT["affirm_calls"] += 1
    sha = _sha256_text(CORE_CREED_TEXT)
    mm = _mm_try_get()

    if mm is None:
        try:
            os.makedirs("data/self", exist_ok=True)
            with open("data/self/core_creed.json", "w", encoding="utf-8") as fh:
                json.dump({"creed": creed_object()}, fh, ensure_ascii=False, indent=2)
            _CNT["affirm_writes"] += 1
            return {"ok": True, "stored": True, "sha": sha, "mode": "file:fallback"}
        except Exception as exc:
            return {"ok": False, "error": f"no memory manager and file write failed: {exc}"}

    if _memory_has_sha(mm, sha):
        _CNT["affirm_skips"] += 1
        return {"ok": True, "stored": False, "sha": sha, "mode": "memory:skip"}

    rec = creed_object()
    stored = False
    used = ""
    for method in ("upsert", "add", "save", "save_text", "insert"):
        fn = getattr(mm, method, None)
        if not fn:
            continue
        try:
            fn(rec) if method in ("upsert", "add", "insert") else fn(rec["text"])
            stored = True
            used = method
            break
        except Exception:
            continue

    if stored:
        _CNT["affirm_writes"] += 1
        return {"ok": True, "stored": True, "sha": sha, "mode": f"memory:{used}"}

    try:
        os.makedirs("data/self", exist_ok=True)
        with open("data/self/core_creed.json", "w", encoding="utf-8") as fh:
            json.dump({"creed": rec}, fh, ensure_ascii=False, indent=2)
        _CNT["affirm_writes"] += 1
        return {"ok": True, "stored": True, "sha": sha, "mode": "memory:fallback_file"}
    except Exception as exc:
        return {"ok": False, "error": f"memory write failed: {exc}"}


def counters() -> Dict[str, int]:
    return dict(_CNT)
