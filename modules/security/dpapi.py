# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes

CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("dpapi_unavailable")


def available() -> bool:
    return os.name == "nt"


def _bytes_to_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    raw = bytes(data or b"")
    buf = ctypes.create_string_buffer(raw, len(raw))
    blob = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    return blob, buf


def _blob_to_bytes(blob: DATA_BLOB) -> bytes:
    if int(blob.cbData) <= 0:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect(plaintext: bytes) -> str:
    _require_windows()
    in_blob, _in_buf = _bytes_to_blob(bytes(plaintext or b""))
    out_blob = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()

    try:
        protected = _blob_to_bytes(out_blob)
    finally:
        if bool(out_blob.pbData):
            kernel32.LocalFree(out_blob.pbData)

    return base64.b64encode(protected).decode("ascii")


def unprotect(b64: str) -> bytes:
    _require_windows()
    try:
        payload = base64.b64decode(str(b64 or "").encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("invalid_base64") from exc

    in_blob, _in_buf = _bytes_to_blob(payload)
    out_blob = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    description = wintypes.LPWSTR()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        ctypes.byref(description),
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()

    try:
        plain = _blob_to_bytes(out_blob)
    finally:
        if bool(out_blob.pbData):
            kernel32.LocalFree(out_blob.pbData)
        if bool(description):
            kernel32.LocalFree(description)

    return plain

