from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_recall_diagnostics_persists_latest_and_history(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    import modules.memory.recall_diagnostics as recall_diagnostics

    recall_diagnostics = importlib.reload(recall_diagnostics)
    result = recall_diagnostics.record_active_bundle(
        query="Что я говорил про пост?",
        user_id="42",
        chat_id="777",
        bundle={
            "schema": "ester.active_memory.v1",
            "stats": {"has_retrieval": True},
            "profile_block": "[ACTIVE_USER_PROFILE]\n- имя: Test User",
            "facts_block": "[ACTIVE_USER_FACTS]\n- Живёт в тестовом городе",
            "retrieval_block": "[ACTIVE_RECALL]\n- важный пост",
            "memory_stance": "[ACTIVE_MEMORY_STANCE]\nНе выдумывай.",
        },
        profile_snapshot={"summary": "Test User: Живёт в тестовом городе."},
        provenance=[{"doc_id": "abc", "path": "D:/docs/post.txt", "page": 1, "offset": 0}],
    )

    latest_path = Path(result["latest_path"])
    history_path = Path(result["history_path"])
    assert latest_path.exists()
    assert history_path.exists()

    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest_payload["schema"] == "ester.recall.diagnostic.v1"
    assert latest_payload["provenance_count"] == 1
    assert latest_payload["sections"]["profile"]
