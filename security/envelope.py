# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
import zipfile
from typing import Optional

from security.signing import hmac_verify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def verify_decrypt_unpack(path: str, target_dir: Optional[str] = None) -> str:
    """"Proverit/raspakovat" konteyner bekapa.
    V tekuschey realizatsii - tolko proverka HMAC (.sig ryadom) i raspakovka ZIP.
    Vozvraschaet put k direktorii raspakovki (target_dir or sgenerirovannoy)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    sig_path = path + ".sig"
    if not os.path.isfile(sig_path):
        raise RuntimeError("signature not found")

    blob = open(path, "rb").read()
    sig = open(sig_path, "r", encoding="ascii").read().strip()
    if not hmac_verify(blob, sig):
        raise RuntimeError("signature mismatch")

    out = target_dir or (path + ".unpacked")
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
        zf.extractall(out)
# return out