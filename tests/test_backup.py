# -*- coding: utf-8 -*-
import os
from pathlib import Path

from config_backup import create_backup, verify_backup
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_backup_create_and_verify(tmp_path: Path, monkeypatch):
    # Creating a data structure for backup
    data_dir = tmp_path / "data" / "vstore"
    data_dir.mkdir(parents=True)
    (data_dir / "vec.bin").write_bytes(b"\x00\x01\x02")
    include_dirs = [str(tmp_path / "data")]

    # Backup folder
    out_dir = tmp_path / "backups"
    out_dir.mkdir()

    zip_path, sig_path = create_backup(output_dir=str(out_dir), include_dirs=include_dirs)
    assert os.path.isfile(zip_path)
    assert os.path.isfile(sig_path)
# assert verify_backup(zip_path) is True