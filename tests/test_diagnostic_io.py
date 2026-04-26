from __future__ import annotations

import json


def test_diagnostic_io_falls_back_when_replace_is_denied(monkeypatch, tmp_path):
    import modules.memory.diagnostic_io as diagnostic_io

    def deny_replace(_tmp: str, _path: str) -> None:
        raise PermissionError("locked")

    monkeypatch.setattr(diagnostic_io.os, "replace", deny_replace)

    json_path = tmp_path / "diag.json"
    text_path = tmp_path / "diag.md"

    diagnostic_io.write_json(str(json_path), {"schema": "test", "value": 3})
    diagnostic_io.write_text(str(text_path), "# ok\n")

    assert json.loads(json_path.read_text(encoding="utf-8"))["value"] == 3
    assert text_path.read_text(encoding="utf-8") == "# ok\n"
    assert not list(tmp_path.glob("*.tmp"))
