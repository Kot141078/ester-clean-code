from __future__ import annotations

import importlib


def _reload_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    import modules.memory.user_facts_store as user_facts_store
    import modules.memory.profile_snapshot as profile_snapshot

    user_facts_store = importlib.reload(user_facts_store)
    profile_snapshot = importlib.reload(profile_snapshot)
    return user_facts_store, profile_snapshot


def test_profile_snapshot_refreshes_from_per_user_facts(monkeypatch, tmp_path):
    user_facts_store, profile_snapshot = _reload_modules(monkeypatch, tmp_path)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе", "Любит чай"])
    snap = profile_snapshot.refresh_profile_snapshot(
        "42",
        display_name="Test User",
        chat_id=777,
        recent_entries=[{"type": "fact", "text": "Пользователь хотел проверить важный пост позже."}],
    )

    assert snap["schema"] == "ester.user_profile_snapshot.v1"
    assert snap["display_name"] == "Test User"
    assert snap["facts"][:2] == ["Живёт в тестовом городе", "Любит чай"]
    assert snap["last_chat_id"] == "777"
    rendered = profile_snapshot.render_profile_context(snap)
    assert "[ACTIVE_USER_PROFILE]" in rendered
    assert "Test User" in rendered


def test_profile_snapshot_refresh_known_profiles_scans_user_fact_files(monkeypatch, tmp_path):
    user_facts_store, profile_snapshot = _reload_modules(monkeypatch, tmp_path)

    user_facts_store.save_user_facts("42", ["Живёт в тестовом городе"])
    user_facts_store.save_user_facts("43", ["Любит кофе"])

    result = profile_snapshot.refresh_known_profiles(limit=10)

    assert result["ok"] is True
    assert set(result["user_ids"]) >= {"42", "43"}
