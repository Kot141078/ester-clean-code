# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from modules.dreams.dream_candidate_seam import (
    build_dream_candidates,
    render_dream_candidates,
    safe_candidate_metadata,
    select_dream_candidates,
)


def test_build_dream_candidates_creates_digest_and_neutral_scores():
    candidates = build_dream_candidates(
        [{"id": "doc-a", "text": "Alpha memory", "meta": {"type": "note"}}],
        source="global",
        meta={"selected_by": "existing_order"},
    )

    assert len(candidates) == 1
    assert candidates[0]["candidate_id"] == "doc-a"
    assert candidates[0]["text"] == "Alpha memory"
    assert len(candidates[0]["text_digest"]) == 64
    assert candidates[0]["base_score"] == 1.0
    assert candidates[0]["score"] == 1.0
    assert candidates[0]["rank_meta"]["selected_by"] == "existing_order"


def test_select_dream_candidates_preserves_existing_order_by_default():
    candidates = build_dream_candidates(
        [{"text": "first"}, {"text": "second"}, {"text": "third"}],
        source="global",
    )

    selected = select_dream_candidates(candidates, limit=2)

    assert [x["text"] for x in selected] == ["first", "second"]
    assert [x["score"] for x in selected] == [1.0, 1.0]


def test_select_dream_candidates_can_follow_existing_order_ids():
    candidates = build_dream_candidates(
        [{"id": "a", "text": "first"}, {"id": "b", "text": "second"}],
        source="global",
    )

    selected = select_dream_candidates(candidates, order=["b", "a"])

    assert [x["candidate_id"] for x in selected] == ["b", "a"]


def test_render_dream_candidates_reproduces_plain_context_output():
    candidates = build_dream_candidates(
        [{"text": "Alpha memory"}, {"text": "Beta memory"}],
        source="global",
    )

    assert render_dream_candidates(candidates) == "Alpha memory\n\nBeta memory"


def test_render_dream_candidates_reproduces_mem_chunk_context_output():
    candidates = build_dream_candidates(
        [{"text": "Alpha memory"}, {"text": "Beta memory"}],
        source="telegram",
    )

    assert render_dream_candidates(candidates, mode="mem_chunks") == "[MEM_1]\nAlpha memory\n\n[MEM_2]\nBeta memory"


def test_safe_candidate_metadata_does_not_include_raw_text_or_secrets():
    candidates = build_dream_candidates(
        [
            {
                "text": "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR",
                "meta": {
                    "prompt": "RAW_PROMPT_SHOULD_NOT_APPEAR",
                    "api_key": "SECRET_TOKEN_SHOULD_NOT_APPEAR",
                    "signal_digest": "safe-digest",
                },
            }
        ],
        source="global",
    )

    safe = safe_candidate_metadata(candidates[0])
    raw = json.dumps(safe, ensure_ascii=False, sort_keys=True)

    assert "text" not in safe
    assert "RAW_DREAM_TEXT_SHOULD_NOT_APPEAR" not in raw
    assert "RAW_PROMPT_SHOULD_NOT_APPEAR" not in raw
    assert "SECRET_TOKEN_SHOULD_NOT_APPEAR" not in raw
    assert safe["text_digest"]


def test_no_attention_bias_is_applied_by_seam(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("attention bias must not be called from seam")

    monkeypatch.setattr("modules.volition.attention_runtime_bridge.get_runtime_attention_bias", boom)

    candidates = build_dream_candidates([{"text": "Alpha memory"}], source="global")
    selected = select_dream_candidates(candidates)

    assert selected[0]["score"] == selected[0]["base_score"] == 1.0


def test_candidate_is_not_deleted_or_suppressed_by_metadata_export():
    candidates = build_dream_candidates([{"id": "doc-a", "text": "Alpha memory"}], source="global")
    selected = select_dream_candidates(candidates, limit=1)
    safe = safe_candidate_metadata(selected[0])

    assert selected[0]["candidate_id"] == "doc-a"
    assert safe["candidate_id"] == "doc-a"
    assert selected[0]["text"] == "Alpha memory"
