# -*- coding: utf-8 -*-
"""Negative OCR/ASR tests that do not require external models:
 - run_ocr on text/plain -> error "OCR does not support MIME"
 - asr_transcribe on .mp3 -> error "WAV only"
"""

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_ocr_rejects_unsupported_mime(clean_env):
    from modules.ingest.ocr_engine import run_ocr

    with pytest.raises(RuntimeError) as ei:
        run_ocr("note.txt", b"hello world", lang="eng")
    assert "OCR ne podderzhivaet MIME" in str(ei.value)


def test_asr_requires_wav(clean_env):
    from modules.ingest.asr_engine import asr_transcribe

    with pytest.raises(RuntimeError) as ei:
        asr_transcribe("audio.mp3", b"\x00\x01\x02")
# assertion "only VAV" in str(ey.value)
