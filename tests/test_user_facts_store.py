from __future__ import annotations

import importlib
import json
from pathlib import Path


def _reload_store(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    import modules.memory.user_facts_store as user_facts_store

    return importlib.reload(user_facts_store)


def test_user_facts_store_is_per_user_and_legacy_optional(monkeypatch, tmp_path):
    user_facts_store = _reload_store(monkeypatch, tmp_path)

    assert user_facts_store.save_user_facts("42", ["Любит чай", "Любит чай"]) is True

    legacy_path = Path(tmp_path) / "data" / "user_facts.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps({"facts": ["Legacy факт"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert user_facts_store.load_user_facts("42", include_legacy=False) == ["Любит чай"]
    assert user_facts_store.load_user_facts("42", include_legacy=True) == ["Любит чай", "Legacy факт"]


def test_user_facts_store_can_sync_owner_legacy_file(monkeypatch, tmp_path):
    user_facts_store = _reload_store(monkeypatch, tmp_path)

    assert user_facts_store.save_user_facts("owner", ["Служил в армии"], sync_legacy=True) is True

    user_file = Path(tmp_path) / "data" / "memory" / "user_facts" / "by_user" / "owner.json"
    legacy_file = Path(tmp_path) / "data" / "user_facts.json"

    user_payload = json.loads(user_file.read_text(encoding="utf-8"))
    legacy_payload = json.loads(legacy_file.read_text(encoding="utf-8"))

    assert user_payload["facts"] == ["Служил в армии"]
    assert legacy_payload["facts"] == ["Служил в армии"]
    assert user_payload["history"]
