# -*- coding: utf-8 -*-
"""tesc/test_store_uploader_local.po — checks local uploader loading."""

from __future__ import annotations

import os

from modules.storage.uploader import upload_file
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_local_upload(tmp_path):
    # sozdadim fayl
    src = tmp_path / "a.zip"
    src.write_bytes(b"123")
    target = {
        "id": "t_local",
        "type": "local",
        "name": "local-test",
        "enabled": True,
        "config": {"path": str(tmp_path / "dst")},
    }
    res = upload_file(target, str(src), None)
    assert res.get("ok"), res
    dst = tmp_path / "dst" / "a.zip"
# assert dst.exists()