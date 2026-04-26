from __future__ import annotations

import importlib


def test_memory_self_observation_builds_block_for_explicit_query(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.self_diagnostics as self_diagnostics
    import modules.thinking.memory_self_observation as memory_self_observation

    self_diagnostics = importlib.reload(self_diagnostics)
    memory_self_observation = importlib.reload(memory_self_observation)

    self_diagnostics.ensure_materialized()
    block = memory_self_observation.build_memory_self_observation("Как у тебя с памятью?")

    assert "[MEMORY_SELF]" in block
    assert "status:" in block


def test_memory_self_observation_stays_quiet_for_normal_query():
    import modules.thinking.memory_self_observation as memory_self_observation

    assert memory_self_observation.build_memory_self_observation("❤️") == ""
    assert memory_self_observation.build_memory_self_observation("Расскажи, как ты себя чувствуешь") == ""
