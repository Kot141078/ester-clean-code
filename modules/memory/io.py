# -*- coding: utf-8 -*-
"""
modules/memory/io.py — ввод/вывод памяти.

Функции:
- save_snapshot(path, data)
- load_snapshot(path)

Фикс:
- атомарная запись НА ТОЙ ЖЕ ФС: temp-файл создаётся в директории назначения и заменяется через os.replace()
- при битом JSON: файл карантинируется (*.corrupt_YYYYMMDD_HHMMSS) и возвращается {}

# c=a+b
"""
from typing import Dict, Any
import os
import json
import tempfile
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def save_snapshot(path: str, data: Dict[str, Any]) -> None:
    """
    Atomic save on the same filesystem:
    - create temp file in target directory
    - write
    - os.replace() to final path (atomic on same FS)
    """
    dir_ = os.path.dirname(path) or "."
    os.makedirs(dir_, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_mem_", suffix=".json", dir=dir_, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # компактно: быстрее пишет, меньше шанс словить полубитый файл при внешнем убийстве процесса
            json.dump(data, f, ensure_ascii=False)
        try:
            os.replace(tmp_path, path)
        except Exception:
            # Windows can deny atomic replace on locked targets; keep behavior by falling back to direct write.
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def load_snapshot(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        # quarantine corrupt file
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bad = f"{path}.corrupt_{stamp}"
        try:
            os.replace(path, bad)
        except Exception:
            try:
                os.rename(path, bad)
            except Exception:
                pass
        return {}
