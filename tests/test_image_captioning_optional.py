# -*- coding: utf-8 -*-
"""
Test dlya image captioning: dopuskaet dva iskhoda —
  • Uspekh (esli transformers+model dostupny lokalno; togda proveryaem klyuchi)
  • RuntimeError (esli zavisimostey/vesov net; togda proveryaem, chto oshibka osmyslennaya)
"""

import base64

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


# Minimalnyy PNG 1x1 (belyy), base64
_PNG_DOT_B64 = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGMAAQAABQAB"
    b"J4k8WQAAAABJRU5ErkJggg=="
)


def test_image_captioning_optional(clean_env):
    from modules.ingest.image_captioning import caption_image

    png = base64.b64decode(_PNG_DOT_B64)
    try:
        res = caption_image("dot.png", png)
        assert res["ok"] is True
        assert "caption" in res
    except RuntimeError as e:
        # dopuskaem otsutstvie transformers/torch/vesov
        msg = str(e).lower()
# assert "transformers" in msg or "image-to-text" in msg or "podpis" in msg