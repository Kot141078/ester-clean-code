from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_SOURCE = (ROOT / "run_ester_fixed.py").read_text(encoding="utf-8")
LISTENER_SOURCE = (ROOT / "listeners" / "telegram_bot.py").read_text(encoding="utf-8")


def _extract_block(source: str, start_pat: str, end_pat: str) -> str:
    match = re.search(start_pat + r".*?" + end_pat, source, re.S)
    assert match, f"block not found: {start_pat} -> {end_pat}"
    return match.group(0)


def test_restore_context_from_passport_uses_shared_dual_schema_normalizer():
    run_block = _extract_block(RUN_SOURCE, r"def restore_context_from_passport\(\):", r"def _migrate_legacy_docs")
    listener_block = _extract_block(LISTENER_SOURCE, r"def restore_context_from_passport\(\):", r"def _tg_lock_path")

    assert "_passport_record_to_short_term_messages(rec)" in run_block
    assert "_passport_record_to_short_term_messages(rec)" in listener_block


def test_run_document_handler_splits_processing_and_delivery_failures():
    block = _extract_block(RUN_SOURCE, r"async def handle_document\(update: Update, context: ContextTypes.DEFAULT_TYPE\):", r"# --- 18\) Vision")

    assert 'accepted_ok = await _tg_reply_with_retry(msg, f"📥 Беру: {orig_name}…", attempts=4)' in block
    assert "[DOC_PIPELINE] reasoning_ready" in block
    assert "[DOC_TG_SEND] accepted_notice_failed" in block
    assert "[DOC_TG_FINAL_SEND] failed" in block
    assert "sent_ok = await send_smart_split(update, resp)" in block
    assert "_document_delivery_failure_notice(orig_name)" in block
    assert "Ошибка восприятия:" not in block


def test_listener_document_handler_matches_honest_delivery_contract():
    block = _extract_block(LISTENER_SOURCE, r"async def handle_document\(update: Update, context: ContextTypes.DEFAULT_TYPE\):", r"# --- 18\) Vision")

    assert 'accepted_ok = await _tg_reply_with_retry(msg, f"📥 Беру: {orig_name}…", attempts=4)' in block
    assert "[DOC_PIPELINE] reasoning_ready" in block
    assert "[DOC_TG_SEND] processed_ack_failed" in block
    assert "[DOC_TG_FINAL_SEND] failed" in block
    assert "sent_ok = await send_smart_split(update, resp)" in block
    assert "_document_delivery_failure_notice(orig_name)" in block
    assert "Ошибка восприятия:" not in block

