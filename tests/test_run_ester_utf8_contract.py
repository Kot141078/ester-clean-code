from __future__ import annotations

from pathlib import Path


def test_run_ester_utf8_exposes_enable_flask_parameter():
    path = Path(__file__).resolve().parents[1] / "tools" / "run_ester_utf8.ps1"
    text = path.read_text(encoding="utf-8")

    assert "[string]$EnableFlask = \"\"" in text
    assert "$env:ESTER_FLASK_ENABLE = $EnableFlask" in text
    assert "Flask/listener mode: ESTER_FLASK_ENABLE=" in text


def test_ollama_launcher_enables_flask_reports():
    path = Path(__file__).resolve().parents[1] / "ester_start_ollama.bat"
    text = path.read_text(encoding="utf-8")

    assert 'run_ester_utf8.ps1" -EnableFlask 1' in text
