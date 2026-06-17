# -*- coding: utf-8 -*-
"""Deterministic state path helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

PathLike = Union[str, os.PathLike[str]]


def _root_from(base: PathLike | None = None) -> Path:
    if base is not None:
        return Path(base).expanduser()
    raw = os.environ.get("ESTER_STATE_DIR") or os.environ.get("PERSIST_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home().joinpath(".ester")


def _safe_child(part: PathLike) -> Path:
    child = Path(part)
    if child.is_absolute() or ".." in child.parts:
        raise ValueError("state path parts must be relative")
    return child


def resolve_state_dir(
    name: PathLike | None = None,
    base: PathLike | None = None,
    create: bool = False,
) -> Path:
    root = _root_from(base)
    path = root if name in (None, "") else root.joinpath(_safe_child(name))
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_state_path(*parts: PathLike, base: PathLike | None = None) -> Path:
    path = resolve_state_dir(base=base)
    for part in parts:
        path = path.joinpath(_safe_child(part))
    return path


__all__ = ["resolve_state_dir", "resolve_state_path"]
