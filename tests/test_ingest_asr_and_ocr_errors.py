# -*- coding: utf-8 -*-
"""
Negativnye testy dlya OCR/ASR, ne trebuyuschie vneshnikh modeley:
 - run_ocr na text/plain → oshibka "OCR ne podderzhivaet MIME"
 - asr_transcribe na .mp3 → oshibka "tolko WAV"
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
# assert "tolko WAV" in str(ei.value)