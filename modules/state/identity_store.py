# -*- coding: utf-8 -*-
"""Small JSON-backed identity profile and anchor store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

_DEFAULT_PROFILE: dict[str, str] = {
    "human_name": "Owner",
    "language": "en",
    "timezone": "UTC",
}


def _state_dir() -> Path:
    base = os.environ.get("ESTER_STATE_DIR")
    if base:
        return Path(base).expanduser().resolve()
    return (Path.cwd() / "data" / "state").resolve()


def _identity_dir(*, create: bool = False) -> Path:
    path = _state_dir() / "identity"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _profile_path() -> Path:
    return _identity_dir() / "profile.json"


def _anchor_path() -> Path:
    return _identity_dir() / "anchor.txt"


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_profile() -> dict[str, Any]:
    path = _profile_path()
    profile: dict[str, Any] = dict(_DEFAULT_PROFILE)
    if not path.exists():
        return profile
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return profile
    if isinstance(loaded, dict):
        for key, value in loaded.items():
            if isinstance(key, str):
                profile[key] = value
    return profile


def save_profile(update: Mapping[str, Any] | None = None) -> dict[str, Any]:
    profile = load_profile()
    if update:
        for key, value in dict(update).items():
            if isinstance(key, str):
                profile[key] = value
    _write_text_atomic(
        _identity_dir(create=True) / "profile.json",
        json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return dict(profile)


def load_anchor() -> str:
    path = _anchor_path()
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def save_anchor(text: str) -> str:
    value = str(text or "").strip()
    _write_text_atomic(_identity_dir(create=True) / "anchor.txt", value)
    return value


__all__ = ["load_anchor", "load_profile", "save_anchor", "save_profile"]
