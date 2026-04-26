from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_memory_index_materializes_empty_baseline(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.memory_index as memory_index

    memory_index = importlib.reload(memory_index)
    result = memory_index.ensure_materialized()

    overview = result["overview"]
    health = result["health"]
    timeline = result["timeline"]
    operator = result["operator"]

    assert overview["schema"] == "ester.memory.overview.v1"
    assert overview["storage"]["users_total"] == 0
    assert health["schema"] == "ester.memory.health.v1"
    assert timeline["schema"] == "ester.memory.timeline.v1"
    assert operator["schema"] == "ester.memory.operator.v1"
    assert timeline["latest_state"]["users_total"] == 0
    assert memory_index.overview_path().exists()


def test_memory_index_reads_seeded_memory_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.active_context as active_context
    import modules.memory.live_recall_benchmark as live_recall_benchmark
    import modules.memory.memory_index as memory_index
    import modules.memory.profile_snapshot as profile_snapshot
    import modules.memory.recall_diagnostics as recall_diagnostics
    import modules.memory.recent_docs as recent_docs
    import modules.memory.restart_continuity_benchmark as restart_continuity_benchmark
    import modules.memory.semantic_consolidation as semantic_consolidation
    import modules.memory.user_facts_store as user_facts_store

    active_context = importlib.reload(active_context)
    live_recall_benchmark = importlib.reload(live_recall_benchmark)
    memory_index = importlib.reload(memory_index)
    profile_snapshot = importlib.reload(profile_snapshot)
    recall_diagnostics = importlib.reload(recall_diagnostics)
    recent_docs = importlib.reload(recent_docs)
    restart_continuity_benchmark = importlib.reload(restart_continuity_benchmark)
    semantic_consolidation = importlib.reload(semantic_consolidation)
    user_facts_store = importlib.reload(user_facts_store)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе"])
    snapshot = profile_snapshot.refresh_profile_snapshot("42", display_name="Test User", chat_id=777)
    bundle = active_context.build_active_memory_bundle(
        user_text="Что ты про меня помнишь?",
        evidence_memory="",
        user_facts=["Живёт в тестовом городе"],
        profile_context=profile_snapshot.render_profile_context(snapshot),
        honesty_block="[ACTIVE_MEMORY_HONESTY]\n- stance: stable\n- confidence: high",
    )
    recall_diagnostics.record_active_bundle(
        query="Что ты про меня помнишь?",
        user_id="42",
        chat_id="777",
        bundle=bundle,
        profile_snapshot=snapshot,
        provenance=[],
    )

    recent_docs.remember_recent_doc(
        777,
        doc_id="doc-1",
        name="Посты.txt",
        summary="Recent summary for Посты.txt with the key post mentioned.",
        citations=["[Посты.txt | p. ?]"],
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
    )
    recent_docs.remember_last_resolved_document(
        777,
        None,
        doc_id="doc-1",
        orig_name="Посты.txt",
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
        reason="recent_bound",
    )

    passport_dir = Path(tmp_path) / "data" / "passport"
    passport_dir.mkdir(parents=True, exist_ok=True)
    (passport_dir / "clean_memory.jsonl").write_text(
        json.dumps({"role_user": "старый вопрос", "role_assistant": "старый ответ"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    live_recall_benchmark.run_live_benchmark(cases=[{"id": "fact", "kind": "first_user_fact"}])
    restart_continuity_benchmark.run_restart_benchmark(
        cases=[
            {"id": "passport", "kind": "passport_tail_restore"},
            {"id": "profile", "kind": "first_user_profile"},
            {"id": "doc", "kind": "first_recent_doc_binding"},
        ]
    )
    semantic_consolidation.run(limit_users=10)

    payload = memory_index.ensure_materialized()
    overview = payload["overview"]
    health = payload["health"]
    operator = payload["operator"]

    assert overview["storage"]["users_total"] >= 1
    assert overview["latest"]["live_benchmark"]["state"] == "passed"
    assert overview["latest"]["restart_continuity"]["state"] == "passed"
    assert overview["latest"]["recall"]["honesty_label"] == "stable"
    assert overview["latest"]["reply_trace"]["state"] in {"missing", "ready"}
    assert overview["latest"]["self_diagnostics"]["state"] in {"missing", "ready"}
    assert health["status_label"] in {"healthy", "attention"}
    assert "missing_recall_diagnostic" not in health["alert_codes"]
    assert operator["schema"] == "ester.memory.operator.v1"
    assert isinstance(operator["top_actions"], list)
    assert isinstance(operator["suggested_queries"], list)
