from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_recall_benchmark_runs_corpus_and_persists_report(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    config_dir = Path(tmp_path) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = config_dir / "recall_benchmark_corpus.json"
    corpus_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "profile_case",
                        "query": "Что ты про меня помнишь?",
                        "profile_context": "[ACTIVE_USER_PROFILE]\n- имя: Test User",
                        "user_facts": ["Живёт в тестовом городе"],
                        "required_sections": ["[ACTIVE_USER_PROFILE]", "[ACTIVE_USER_FACTS]"],
                        "required_substrings": ["Живёт в тестовом городе"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    import modules.memory.recall_benchmark as recall_benchmark

    recall_benchmark = importlib.reload(recall_benchmark)
    result = recall_benchmark.run_benchmark()

    assert result["ok"] is True
    report = result["report"]
    assert report["schema"] == "ester.recall.benchmark.v1"
    assert report["cases_failed"] == 0
