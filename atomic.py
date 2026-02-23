# -*- coding: utf-8 -*-
from __future__ import annotations

"""
atomic.py — atomarnaya zapis faylov (bytes/text/json) + chtenie JSON.

Tseli:
- pisat cherez vremennyy fayl v toy zhe direktorii i os.replace() (atomarno na Windows/Unix dlya obychnykh FS);
- po zhelaniyu delat bekap predyduschey versii;
- maksimalno snizit risk «polupustogo fayla» pri sboyakh pitaniya: flush + fsync fayla, i (na POSIX) fsync direktorii;
- chtenie JSON ustoychivo k BOM (UTF-8 BOM) i chastichno bitym faylam (vozvraschaet default).

Vazhno:
- Atomarnost garantiruetsya tolko pri zamene vnutri *odnoy* faylovoy sistemy (tmp sozdaetsya v toy zhe papke).
- fsync direktorii rabotaet na POSIX; na Windows obychno ne trebuetsya/ne podderzhivaetsya — my molcha ignoriruem.
"""

import io
import json
import os
import tempfile
import time
from typing import Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _ensure_dir_for_file(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def _backup_name(path: str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    return f"{path}.bak.{ts}"


def _atomic_replace(tmp_path: str, dst_path: str) -> None:
    # os.replace — atomarnaya zamena na podderzhivaemykh FS (Windows/Unix).
    os.replace(tmp_path, dst_path)


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def _fsync_dir(dir_path: str) -> None:
    """Fsync direktorii (POSIX) — pomogaet «dotaschit» rename/replace pri sboe pitaniya."""
    try:
        fd = os.open(dir_path, os.O_DIRECTORY)
    except Exception:
        return
    try:
        os.fsync(fd)
    except Exception:
        pass
    finally:
        try:
            os.close(fd)
        except Exception:
            pass


def atomic_write_bytes(path: str, data: bytes, make_backup: bool = True) -> None:
    """
    Atomarno zapisyvaet bytes v fayl.
    1) sozdaet tmp v toy zhe direktorii
    2) pishet data, flush + fsync
    3) pri make_backup=True perenosit staryy fayl v .bak.TIMESTAMP
    4) os.replace(tmp, path)
    5) (POSIX) fsync direktorii
    """
    _ensure_dir_for_file(path)
    dir_ = os.path.dirname(path) or "."
    base = os.path.basename(path) or "file"

    fd, tmp = tempfile.mkstemp(prefix=base + ".tmp.", dir=dir_)
    try:
        with os.fdopen(fd, "wb", closefd=True) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if make_backup and os.path.exists(path):
            try:
                os.replace(path, _backup_name(path))
            except Exception:
                # esli bekap ne udalsya — eto ne povod ronyat zapis
                pass

        _atomic_replace(tmp, path)

        # Podtyagivaem operatsiyu replace/rename v zhurnal FS (POSIX).
        _fsync_dir(dir_)

    finally:
        _safe_unlink(tmp)


def atomic_write_text(
    path: str,
    text: str,
    encoding: str = "utf-8",
    make_backup: bool = True,
) -> None:
    atomic_write_bytes(path, text.encode(encoding), make_backup=make_backup)


def atomic_write_json(
    path: str,
    obj: Any,
    encoding: str = "utf-8",
    make_backup: bool = True,
    **json_kwargs: Any,
) -> None:
    """
    Atomarno pishet JSON.
    Po umolchaniyu — chelovekochitaemo (indent=2) i bez ASCII-ekranirovaniya.
    """
    if "ensure_ascii" not in json_kwargs:
        json_kwargs["ensure_ascii"] = False
    if "indent" not in json_kwargs and "separators" not in json_kwargs:
        json_kwargs["indent"] = 2

    text = json.dumps(obj, **json_kwargs)
    # Nebolshoy «shtrikh»: JSON-fayly udobnee diffat s finalnym \n
    if not text.endswith("\n"):
        text += "\n"
    atomic_write_text(path, text, encoding=encoding, make_backup=make_backup)


def read_json(path: str, default: Any = None, encoding: str = "utf-8") -> Any:
    """
    Chitaet JSON iz fayla. Esli fayla net ili on bityy — vozvraschaet default.
    Umeet perezhivat UTF-8 BOM (tipovaya problema pri «pochinili v bloknote»).
    """
    if not os.path.exists(path):
        return default

    # 1) Pytaemsya obychnym sposobom
    try:
        with io.open(path, "r", encoding=encoding) as f:
            return json.load(f)
    except Exception:
        pass

    # 2) Fallback: BOM/musor v nachale. Chitaem kak tekst i chistim.
    try:
        with io.open(path, "r", encoding="utf-8-sig") as f:
            s = f.read()
        s = s.lstrip("\ufeff").strip()
        if not s:
            return default
        return json.loads(s)
    except Exception:
        return default


def read_text(path: str, default: Optional[str] = None, encoding: str = "utf-8") -> Optional[str]:
    if not os.path.exists(path):
        return default
    try:
        with io.open(path, "r", encoding=encoding) as f:
            return f.read()
    except Exception:
        return default