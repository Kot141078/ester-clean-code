# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from modules.dreams import dream_candidate_seam
from modules.dreams.dream_candidate_seam import (
    build_dream_candidates,
    render_preserved_plain_context,
    safe_candidate_metadata,
    select_dream_candidates,
)


def _legacy_plain(raw_items, limit=None, separator="\n\n") -> str:
    chunks = []
    for item in list(raw_items or []):
        text = str((item or {}).get("text") or (item or {}).get("summary") or (item or {}).get("title") or "").strip()
        if not text:
            continue
        chunks.append(text)
        if limit is not None and len(chunks) >= max(0, int(limit)):
            break
    return str(separator).join(chunks).strip()


def test_controlled_raw_docs_preserve_legacy_plain_output_byte_for_byte():
    raw_docs = [
        {"text": "Alpha memory", "meta": {"type": "note"}},
        {"text": "Beta memory\nwith line", "meta": {"type": "dream"}},
        {"text": "  Gamma memory  ", "meta": {"type": "note"}},
    ]

    rendered = render_preserved_plain_context(raw_docs, source="global_vector", limit=3)

    assert rendered == _legacy_plain(raw_docs, limit=3)


def test_existing_order_and_cap_are_preserved_by_plain_seam():
    raw_docs = [
        {"id": "a", "text": "first", "meta": {"source": "one"}},
        {"id": "b", "text": "second", "meta": {"source": "two"}},
        {"id": "c", "text": "third", "meta": {"source": "three"}},
    ]

    rendered = render_preserved_plain_context(raw_docs, source="global_vector", limit=2)

    assert rendered == "first\n\nsecond"


def test_candidate_score_remains_neutral_in_extraction_seam():
    candidates = build_dream_candidates([{"text": "Alpha memory"}], source="global_vector")
    selected = select_dream_candidates(candidates, limit=1)

    assert selected[0]["base_score"] == 1.0
    assert selected[0]["score"] == 1.0


def test_apply_dream_env_does_not_call_attention_bias(monkeypatch):
    monkeypatch.setenv("ESTER_ATTENTION_REBALANCE_APPLY_DREAM", "1")

    def boom(*_args, **_kwargs):
        raise AssertionError("attention bias must not be called by the seam")

    monkeypatch.setattr("modules.volition.attention_runtime_bridge.get_runtime_attention_bias", boom)

    rendered = render_preserved_plain_context([{"text": "Alpha memory"}], source="global_vector", limit=1)

    assert rendered == "Alpha memory"


def test_candidate_is_not_deleted_or_suppressed():
    candidates = build_dream_candidates(
        [{"id": "doc-a", "text": "Alpha memory"}, {"id": "doc-b", "text": "Beta memory"}],
        source="global_vector",
    )
    selected = select_dream_candidates(candidates, limit=2)

    assert [row["candidate_id"] for row in selected] == ["doc-a", "doc-b"]
    assert [row["text"] for row in selected] == ["Alpha memory", "Beta memory"]


def test_safe_metadata_excludes_raw_text_and_sensitive_keys():
    candidates = build_dream_candidates(
        [
            {
                "id": "doc-a",
                "text": "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR",
                "meta": {
                    "api_key": "SECRET_TOKEN_SHOULD_NOT_APPEAR",
                    "payload": "RAW_PAYLOAD_SHOULD_NOT_APPEAR",
                    "signal_digest": "safe-signal",
                },
            }
        ],
        source="global_vector",
    )

    safe = safe_candidate_metadata(candidates[0])
    raw = json.dumps(safe, ensure_ascii=False, sort_keys=True)

    assert "text" not in safe
    assert "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw
    assert "RAW_PAYLOAD_SHOULD_NOT_APPEAR" not in raw
    assert safe["text_digest"]


def test_helper_failure_path_preserves_legacy_plain_output(monkeypatch):
    raw_docs = [{"text": "Alpha memory"}, {"text": "Beta memory"}]

    def boom(*_args, **_kwargs):
        raise RuntimeError("candidate seam unavailable")

    monkeypatch.setattr(dream_candidate_seam, "build_dream_candidates", boom)

    rendered = render_preserved_plain_context(raw_docs, source="global_vector", limit=2)

    assert rendered == _legacy_plain(raw_docs, limit=2)
