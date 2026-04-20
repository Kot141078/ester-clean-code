from __future__ import annotations

from modules.telegram_runtime_helpers import document_delivery_failure_notice
from modules.telegram_runtime_helpers import passport_record_to_short_term_messages


def test_passport_record_to_short_term_messages_supports_both_dialog_schemas():
    legacy = passport_record_to_short_term_messages(
        {
            "role_user": "legacy user",
            "role_assistant": "legacy assistant",
        }
    )
    modern = passport_record_to_short_term_messages(
        {
            "user": "modern user",
            "assistant": "modern assistant",
        }
    )

    assert legacy == [
        {"role": "user", "content": "legacy user"},
        {"role": "assistant", "content": "legacy assistant"},
    ]
    assert modern == [
        {"role": "user", "content": "modern user"},
        {"role": "assistant", "content": "modern assistant"},
    ]


def test_document_delivery_failure_notice_is_honest_about_telegram_delivery():
    text = document_delivery_failure_notice("report.pdf")

    assert "report.pdf" in text
    assert "не смогла доставить" in text
    assert "Telegram" in text

