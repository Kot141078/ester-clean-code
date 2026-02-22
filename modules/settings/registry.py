# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple


@dataclass(frozen=True)
class SettingDef:
    key: str
    group: str
    type: str
    default: Any
    description: str
    min: float | None = None
    max: float | None = None
    choices: Tuple[str, ...] = ()
    is_sensitive: bool = False
    requires_restart: bool = False


_REGISTRY: Tuple[SettingDef, ...] = (
    SettingDef(
        key="ui.autolaunch",
        group="ui",
        type="bool",
        default=True,
        description="Auto-open admin portal in browser at startup.",
    ),
    SettingDef(
        key="ui.portal_url",
        group="ui",
        type="str",
        default="/admin/portal",
        description="Portal URL or absolute URL for auto-launch.",
    ),
    SettingDef(
        key="ui.language",
        group="ui",
        type="str",
        default="ru",
        description="Default language for UI hints.",
    ),
    SettingDef(
        key="ui.timezone",
        group="ui",
        type="str",
        default="UTC",
        description="Timezone used in user-facing timestamps.",
    ),
    SettingDef(
        key="rag.topn",
        group="rag",
        type="int",
        default=20,
        min=5,
        max=200,
        description="Top-N retrieval depth.",
    ),
    SettingDef(
        key="rag.lambda",
        group="rag",
        type="float",
        default=0.35,
        min=0.0,
        max=1.0,
        description="Hybrid retrieval blend factor.",
    ),
    SettingDef(
        key="rag.use_hybrid",
        group="rag",
        type="bool",
        default=True,
        description="Enable hybrid retrieval mode.",
    ),
    SettingDef(
        key="memory.recent_days",
        group="memory",
        type="int",
        default=30,
        min=1,
        max=90,
        description="Recent memory window in days.",
    ),
    SettingDef(
        key="memory.max_items",
        group="memory",
        type="int",
        default=1500,
        min=100,
        max=10000,
        description="In-memory cap for recent records.",
        requires_restart=True,
    ),
    SettingDef(
        key="logs.level",
        group="logs",
        type="choice",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        description="Application log level.",
        requires_restart=True,
    ),
    SettingDef(
        key="logs.json",
        group="logs",
        type="bool",
        default=False,
        description="Emit JSON logs.",
        requires_restart=True,
    ),
    SettingDef(
        key="runtime.request_timeout_sec",
        group="runtime",
        type="int",
        default=60,
        min=1,
        max=600,
        description="Default request timeout in seconds.",
    ),
    SettingDef(
        key="runtime.safe_mode",
        group="runtime",
        type="bool",
        default=True,
        description="Keep strict runtime guards enabled.",
        requires_restart=True,
    ),
)

_BY_KEY: Dict[str, SettingDef] = {item.key: item for item in _REGISTRY}
if len(_BY_KEY) != len(_REGISTRY):
    raise RuntimeError("settings_registry_duplicate_keys")


def all_settings() -> List[SettingDef]:
    return list(_REGISTRY)


def defaults_map() -> Dict[str, Any]:
    return {item.key: item.default for item in _REGISTRY}


def get_setting(key: str) -> SettingDef | None:
    return _BY_KEY.get(str(key or "").strip())


def group_names() -> List[str]:
    return sorted({item.group for item in _REGISTRY})


def settings_for_group(group: str) -> List[SettingDef]:
    clean = str(group or "").strip()
    return [item for item in _REGISTRY if item.group == clean]


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    raise ValueError("invalid_bool")


def validate_value(key: str, value: Any) -> Tuple[bool, Any, str]:
    item = get_setting(key)
    if item is None:
        return False, None, "unknown_key"

    try:
        if item.type == "bool":
            out = _parse_bool(value)
        elif item.type == "int":
            out = int(value)
            if item.min is not None and out < int(item.min):
                raise ValueError("below_min")
            if item.max is not None and out > int(item.max):
                raise ValueError("above_max")
        elif item.type == "float":
            out = float(value)
            if item.min is not None and out < float(item.min):
                raise ValueError("below_min")
            if item.max is not None and out > float(item.max):
                raise ValueError("above_max")
        elif item.type == "choice":
            out = str(value or "").strip().upper()
            if not out:
                raise ValueError("empty_choice")
            allowed = tuple(str(x).upper() for x in item.choices)
            if out not in allowed:
                raise ValueError("invalid_choice")
        else:
            out = str(value or "").strip()
            if len(out) > 2048:
                raise ValueError("too_long")
            if not out:
                out = str(item.default)
        return True, out, ""
    except Exception as exc:
        return False, None, str(exc)


def validate_many(values: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    ok: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for raw_key, raw_value in dict(values or {}).items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        valid, coerced, error = validate_value(key, raw_value)
        if valid:
            ok[key] = coerced
        else:
            errors[key] = error or "invalid_value"
    return ok, errors


def is_known_group(group: str) -> bool:
    return str(group or "").strip() in {item.group for item in _REGISTRY}


def all_keys() -> Iterable[str]:
    return _BY_KEY.keys()

