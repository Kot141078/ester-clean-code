# -*- coding: utf-8 -*-
"""
modules/self/papa_passport.py — profile snapshot from Web UI identity settings.

Compatibility note:
- Function names keep legacy `papa_*` naming to avoid breaking imports.
- Actual values are loaded from `modules.state.identity_store`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, List

from modules.state.identity_store import load_profile

PAPA_AB = (os.getenv("PAPA_AB", "A") or "A").upper()


def _csv_list(value: str) -> List[str]:
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


def _sha256(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _profile_core() -> Dict[str, Any]:
    profile = load_profile()
    name = str(profile.get("human_name") or "Owner").strip() or "Owner"
    aliases = _csv_list(str(profile.get("owner_aliases") or ""))
    if name and name not in aliases:
        aliases.insert(0, name)
    return {
        "name_canonical": name,
        "name_native": name,
        "birth_date": str(profile.get("owner_birth_date") or ""),
        "personal_code": str(profile.get("owner_personal_code") or ""),
        "birth_place": str(profile.get("owner_birth_place") or ""),
        "citizenship": _csv_list(str(profile.get("owner_citizenship") or "")),
        "priority_statement": str(profile.get("owner_priority_statement") or ""),
        "aliases": aliases,
        "anchor_terms": _csv_list(str(profile.get("anchor_terms") or "")),
    }


def papa_passport() -> Dict[str, Any]:
    core = _profile_core()
    prov = {
        "source": "identity_web_ui",
        "ts": int(time.time()),
        "tags": ["ester:core", "owner:profile", "sensitive"],
    }
    doc = {
        "profile": {
            "name_canonical": core["name_canonical"],
            "name_native": core["name_native"],
            "birth_date": core["birth_date"],
            "personal_code": core["personal_code"],
            "birth_place": core["birth_place"],
            "citizenship": core["citizenship"],
            "priority_statement": core["priority_statement"],
        },
        "aliases": core["aliases"],
        "anchor_terms": core["anchor_terms"],
        "meta": {"provenance": prov, "kind": "owner_profile", "importance": 1.0},
    }
    doc["sha256"] = _sha256(doc)
    return doc


def papa_fingerprint() -> Dict[str, Any]:
    doc = papa_passport()
    h = doc["sha256"]
    b32 = base64.b32encode(bytes.fromhex(h)).decode("ascii").rstrip("=")
    return {"ok": True, "sha256": h, "base32": b32, "short": h[:12].upper(), "provenance": doc["meta"]["provenance"]}


def _mm():
    try:
        from services.mm_access import get_mm  # type: ignore

        return get_mm()
    except Exception:
        return None


def _memory_has_sha(mm: Any, sha: str) -> bool:
    try:
        res = getattr(mm, "search", None) or getattr(mm, "find", None)
        if not res:
            return False
        items = (res(q=sha, k=5) or {}).get("items", [])
        for row in items:
            meta = dict((row or {}).get("meta") or {})
            prov = dict(meta.get("provenance") or {})
            if prov.get("sha256") == sha or meta.get("sha256") == sha:
                return True
    except Exception:
        return False
    return False


def affirm() -> Dict[str, Any]:
    """Idempotently persist owner profile snapshot to memory (or local file fallback)."""
    if PAPA_AB == "B":
        return {"ok": True, "stored": False, "reason": "PAPA_AB=B"}

    doc = papa_passport()
    h = str(doc.get("sha256") or "")
    mm = _mm()

    if mm is not None and h and _memory_has_sha(mm, h):
        return {"ok": True, "stored": False, "sha256": h, "mode": "memory:skip"}

    stored = False
    mode = "unknown"
    if mm is not None:
        for meth in ("upsert", "add", "insert", "save"):
            fn = getattr(mm, meth, None)
            if not fn:
                continue
            try:
                fn(doc)
                stored = True
                mode = f"memory:{meth}"
                break
            except Exception:
                continue

    if not stored:
        path = "data/self/owner_profile.json"
        os.makedirs("data/self", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        stored = True
        mode = "file:fallback"

    return {"ok": True, "stored": stored, "sha256": h, "mode": mode}

