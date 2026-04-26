# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict


def _replace_tmp(tmp: str, path: str, direct_write) -> None:
    try:
        os.replace(tmp, path)
    except PermissionError:
        # Windows can deny replacing a diagnostics file while another process
        # is reading it. These are derived sidecars, so prefer a direct rewrite
        # over breaking operator/HTTP materialization.
        direct_write()
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def write_json(path: str, payload: Dict[str, Any]) -> None:
    dir_ = os.path.dirname(path) or "."
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=dir_,
        text=True,
    )
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    def _direct_write() -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    _replace_tmp(tmp, path, _direct_write)


def write_text(path: str, text: str) -> None:
    dir_ = os.path.dirname(path) or "."
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=dir_,
        text=True,
    )
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(str(text or ""))

    def _direct_write() -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(str(text or ""))

    _replace_tmp(tmp, path, _direct_write)


__all__ = ["write_json", "write_text"]
