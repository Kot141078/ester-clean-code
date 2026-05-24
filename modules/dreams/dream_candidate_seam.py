# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from typing import Any, Dict, List

_SENSITIVE_TOKENS = ("api_key", "apikey", "authorization", "password", "payload", "prompt", "secret", "token")


def _safe_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _digest_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8", errors="ignore")).hexdigest()


def _safe_meta(src: Any) -> Dict[str, Any]:
    if not isinstance(src, dict):
        return {}
    allowed = {
        "candidate_id",
        "kind",
        "original_index",
        "policy_hit",
        "reason_code",
        "selected_by",
        "signal_digest",
        "source",
        "source_cap",
        "summary_digest",
        "type",
    }
    out: Dict[str, Any] = {}
    for key, value in src.items():
        name = str(key or "")
        low = name.lower()
        if name not in allowed:
            continue
        if any(tok in low for tok in _SENSITIVE_TOKENS) and not low.endswith("_digest"):
            continue
        if isinstance(value, (bool, int, float)) or value is None:
            out[name] = value
        else:
            out[name] = _safe_text(value, 160)
    return out


def _raw_item_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or item.get("summary") or item.get("title") or "").strip()
    return str(item or "").strip()


def _candidate_id(source: str, index: int, text_digest: str) -> str:
    prefix = _safe_text(source, 32).replace(" ", "_") or "dream"
    return f"{prefix}_{int(index)}_{text_digest[:12]}"


def build_dream_candidates(
    raw_items: list[dict],
    *,
    source: str = "",
    meta: dict | None = None,
) -> list[dict]:
    """Normalize raw dream source items into transient candidates.

    This seam exists before runtime bias: raw text is kept only in memory so render can preserve output.
    """

    common_meta = _safe_meta(meta or {})
    src = _safe_text(source or common_meta.get("source") or "dream", 80) or "dream"
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(list(raw_items or [])):
        row = dict(item or {}) if isinstance(item, dict) else {"text": item}
        text = _raw_item_text(row)
        if not text:
            continue
        row_meta = _safe_meta(row.get("meta") or {})
        merged_meta = dict(common_meta)
        merged_meta.update(row_meta)
        kind = _safe_text(row.get("kind") or merged_meta.get("kind") or row.get("type") or "doc", 40) or "doc"
        digest = _safe_text(row.get("text_digest") or row.get("digest") or "", 128) or _digest_text(text)
        candidate_id = _safe_text(row.get("candidate_id") or row.get("id") or "", 160) or _candidate_id(
            src, idx, digest
        )
        # Neutral scores are placeholders for a future audited APPLY_DREAM hook; no bias is applied here.
        out.append(
            {
                "candidate_id": candidate_id,
                "source": src,
                "kind": kind,
                "text": text,
                "text_digest": digest,
                "summary": _safe_text(row.get("summary") if row.get("summary") != text else "", 160),
                "base_score": 1.0,
                "score": 1.0,
                "rank_meta": {
                    "original_index": int(row.get("original_index") or idx),
                    "source_cap": _safe_text(merged_meta.get("source_cap"), 80),
                    "selected_by": _safe_text(merged_meta.get("selected_by") or "existing_order", 80),
                },
                "meta": merged_meta,
            }
        )
    return out


def select_dream_candidates(
    candidates: list[dict],
    *,
    caps: dict | None = None,
    order: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Select candidates without applying attention bias or changing scores."""

    rows = [dict(c or {}) for c in list(candidates or []) if isinstance(c, dict)]
    if order:
        rank = {str(cid): i for i, cid in enumerate(order)}
        rows.sort(key=lambda c: rank.get(str(c.get("candidate_id") or ""), len(rank)))
    per_source = None
    if isinstance(caps, dict) and caps.get("per_source") is not None:
        try:
            per_source = max(1, int(caps.get("per_source")))
        except Exception:
            per_source = None
    selected: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    for row in rows:
        src = str(row.get("source") or "")
        if per_source is not None and src:
            cur = int(source_counts.get(src, 0))
            if cur >= per_source:
                continue
            source_counts[src] = cur + 1
        # Selection never deletes or suppresses the source object; it returns a bounded view.
        selected.append(row)
        if limit is not None and len(selected) >= max(0, int(limit)):
            break
    return selected


def render_dream_candidates(
    candidates: list[dict],
    *,
    mode: str = "plain",
    separator: str = "\n\n",
    max_chars: int | None = None,
) -> str:
    """Render transient candidates back to current dream context text formats."""

    rows = [dict(c or {}) for c in list(candidates or []) if isinstance(c, dict)]
    chunks: List[str] = []
    total = 0
    for idx, row in enumerate(rows, start=1):
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        chunk = f"[MEM_{idx}]\n{text}\n" if mode == "mem_chunks" else text
        if max_chars is not None and total + len(chunk) > int(max_chars):
            break
        chunks.append(chunk)
        total += len(chunk)
    joiner = "\n" if mode == "mem_chunks" else str(separator)
    return joiner.join(chunks).strip()


def render_preserved_plain_context(
    raw_items: list[dict],
    *,
    source: str = "",
    limit: int | None = None,
    separator: str = "\n\n",
    meta: dict | None = None,
) -> str:
    """Use the candidate seam while preserving the legacy plain context render."""

    def _legacy_render() -> str:
        chunks: List[str] = []
        for item in list(raw_items or []):
            text = _raw_item_text(item)
            if not text:
                continue
            chunks.append(text)
            if limit is not None and len(chunks) >= max(0, int(limit)):
                break
        return str(separator).join(chunks).strip()

    try:
        candidates = build_dream_candidates(raw_items, source=source, meta=meta)
        selected = select_dream_candidates(candidates, limit=limit)
        return render_dream_candidates(selected, mode="plain", separator=separator)
    except Exception:
        return _legacy_render()


def safe_candidate_metadata(candidate: dict) -> dict:
    """Return persistable metadata without transient raw text."""

    c = dict(candidate or {})
    return {
        "candidate_id": _safe_text(c.get("candidate_id"), 160),
        "source": _safe_text(c.get("source"), 80),
        "kind": _safe_text(c.get("kind"), 40),
        "text_digest": _safe_text(c.get("text_digest"), 128),
        "summary": _safe_text(c.get("summary"), 160),
        "base_score": float(c.get("base_score") or 1.0),
        "score": float(c.get("score") or 1.0),
        "rank_meta": _safe_meta(c.get("rank_meta") or {}),
        "meta": _safe_meta(c.get("meta") or {}),
    }


__all__ = [
    "build_dream_candidates",
    "render_dream_candidates",
    "render_preserved_plain_context",
    "safe_candidate_metadata",
    "select_dream_candidates",
]
