from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_restart_continuity_benchmark_persists_passport_profile_and_recent_doc_checks(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.user_facts_store as user_facts_store
    import modules.memory.profile_snapshot as profile_snapshot
    import modules.memory.recent_docs as recent_docs
    import modules.memory.restart_continuity_benchmark as restart_continuity_benchmark

    user_facts_store = importlib.reload(user_facts_store)
    profile_snapshot = importlib.reload(profile_snapshot)
    recent_docs = importlib.reload(recent_docs)
    restart_continuity_benchmark = importlib.reload(restart_continuity_benchmark)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе"])
    profile_snapshot.refresh_profile_snapshot("42", display_name="Test User", chat_id=777)

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
        "\n".join(
            [
                json.dumps({"role_user": "старый вопрос", "role_assistant": "старый ответ"}, ensure_ascii=False),
                json.dumps({"user": "новый вопрос", "assistant": "новый ответ"}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = restart_continuity_benchmark.run_restart_benchmark()
    report = result["report"]

    assert report["schema"] == "ester.restart_continuity.benchmark.v1"
    assert report["cases_failed"] == 0
    assert report["cases_passed"] >= 3
    assert Path(result["latest_path"]).exists()
