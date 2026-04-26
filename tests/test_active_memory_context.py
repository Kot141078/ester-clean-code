from __future__ import annotations

from modules.memory.active_context import build_active_memory_bundle


def test_active_memory_bundle_layers_recall_and_filters_internal_recent_entries():
    bundle = build_active_memory_bundle(
        user_text="Что я говорил про тот пост?",
        evidence_memory="[FLASHBACK]\n- (fact) Пользователь хотел проверить важный пост позже.",
        profile_context="[ACTIVE_USER_PROFILE]\n- имя: Test User\n- факт: Живёт в тестовом городе",
        honesty_block="[ACTIVE_MEMORY_HONESTY]\n- stance: mixed\n- confidence: medium",
        user_facts=["Живёт в тестовом городе"],
        recent_entries=[
            {
                "type": "fact",
                "text": "[DISCOVERY_SCAN] found=750",
                "meta": {"source": "discovery_loader", "scope": "internal"},
            },
            {
                "type": "fact",
                "text": "Пользователь хотел проверить важный пост позже.",
                "meta": {"chat_id": "777", "user_id": "42"},
            },
        ],
        recent_doc_context="[DOC]\nПосты.txt: summary for follow-up.",
    )

    context = bundle["context"]
    assert bundle["schema"] == "ester.active_memory.v1"
    assert "[ACTIVE_USER_PROFILE]" in context
    assert "[ACTIVE_MEMORY_HONESTY]" in context
    assert "[ACTIVE_USER_FACTS]" in context
    assert "[ACTIVE_RECENT_FACTS]" in context
    assert "[ACTIVE_RECALL]" in context
    assert "[ACTIVE_RECENT_DOCUMENT]" in context
    assert "[ACTIVE_MEMORY_STANCE]" in context
    assert "[DISCOVERY_SCAN]" not in context
    assert "Живёт в тестовом городе" in context


def test_active_memory_bundle_reports_sparse_memory_honestly():
    bundle = build_active_memory_bundle(
        user_text="Привет",
        evidence_memory="",
        user_facts=[],
        recent_entries=[],
    )

    assert "Релевантная активная память" in bundle["memory_stance"]
    assert bundle["stats"]["has_retrieval"] is False
