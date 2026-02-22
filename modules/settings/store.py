# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from modules.state.io import read_json_or_default, write_json_atomic
from modules.state.paths import resolve_state_path

from .registry import defaults_map, get_setting, validate_many


def _settings_path() -> Path:
    return resolve_state_path("settings", "settings.json")


def _load_raw() -> Dict[str, Any]:
    value = read_json_or_default(_settings_path(), {})
    if isinstance(value, dict):
        return dict(value)
    return {}


def load_all() -> Dict[str, Any]:
    defaults = defaults_map()
    stored = _load_raw()
    out = dict(defaults)
    for key, value in stored.items():
        if get_setting(key) is None:
            continue
        out[key] = value
    return out


def get(key: str, default: Any = None) -> Any:
    clean_key = str(key or "").strip()
    if not clean_key:
        return default
    value = load_all()
    if clean_key in value:
        return value[clean_key]
    item = get_setting(clean_key)
    if item is not None:
        return item.default
    return default


def set_many(values: Mapping[str, Any]) -> Dict[str, Any]:
    valid, errors = validate_many(values or {})
    if errors:
        return {"ok": False, "saved": 0, "errors": errors}
    if not valid:
        return {"ok": True, "saved": 0, "errors": {}}

    merged = load_all()
    merged.update(valid)
    to_write = {k: merged[k] for k in defaults_map().keys()}
    write_json_atomic(_settings_path(), to_write)
    return {"ok": True, "saved": len(valid), "errors": {}}


def file_path() -> Path:
    return _settings_path()

