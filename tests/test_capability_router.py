from __future__ import annotations

from modules.capabilities import router


def test_image_route_uses_dedicated_vision_model(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_MODEL", "qwen2.5:32b")
    monkeypatch.setenv("ESTER_VISION_MODEL", "qwen2.5vl:7b")
    route = router.route_for("image")
    assert route["provider"] == "local"
    assert route["model"] == "qwen2.5vl:7b"
    assert route["stage"] == "vision_model_to_description_to_chat_model"


def test_speech_route_reports_stt_and_tts(monkeypatch):
    monkeypatch.setenv("STT_ENABLE", "1")
    monkeypatch.setenv("STT_MODEL", "small")
    monkeypatch.setenv("ESTER_TG_TTS_COMMAND_ENABLED", "1")
    route = router.route_for("speech")
    assert route["stt"]["enabled"] is True
    assert route["stt"]["model"] == "small"
    assert route["tts"]["telegram_command_enabled"] is True
