# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from modules.state.io import atomic_write_text
from modules.state.paths import resolve_state_path

from . import dpapi

SUPPORTED_PROVIDERS: List[str] = [
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "SERPAPI_KEY",
]


def _vault_path() -> Path:
    return resolve_state_path("vault", "secrets.json.dpapi")


def _last4(secret: str) -> str:
    value = str(secret or "")
    if not value:
        return ""
    if len(value) <= 4:
        return value
    return value[-4:]


def _load_plain() -> Dict[str, str]:
    path = _vault_path()
    if not path.exists():
        return {}
    blob = path.read_text(encoding="utf-8").strip()
    if not blob:
        return {}
    clear = dpapi.unprotect(blob).decode("utf-8")
    loaded = json.loads(clear)
    if not isinstance(loaded, Mapping):
        return {}
    out: Dict[str, str] = {}
    for key, value in loaded.items():
        key_str = str(key or "").strip()
        if not key_str:
            continue
        out[key_str] = str(value or "")
    return out


def _write_plain(data: Mapping[str, str]) -> None:
    blob = dpapi.protect(json.dumps(dict(data), ensure_ascii=False, sort_keys=True).encode("utf-8"))
    atomic_write_text(_vault_path(), blob + "\n", encoding="utf-8")


def vault_status() -> Dict[str, Any]:
    if not dpapi.available():
        return {"ok": False, "enabled": False, "error": "dpapi_unavailable"}
    return {"ok": True, "enabled": True, "path": str(_vault_path())}


def get_secret(name: str) -> str:
    if not dpapi.available():
        return ""
    try:
        return str(_load_plain().get(str(name or "").strip(), "") or "")
    except Exception:
        return ""


def set_secret(name: str, value: str) -> Dict[str, Any]:
    provider = str(name or "").strip()
    secret = str(value or "").strip()
    if not provider:
        return {"ok": False, "error": "provider_required"}
    if not secret:
        return {"ok": False, "error": "secret_required"}
    if not dpapi.available():
        return {"ok": False, "error": "dpapi_unavailable"}

    data = _load_plain()
    data[provider] = secret
    _write_plain(data)
    return {"ok": True, "provider": provider, "set": True, "last4": _last4(secret)}


def unset_secret(name: str) -> Dict[str, Any]:
    provider = str(name or "").strip()
    if not provider:
        return {"ok": False, "error": "provider_required"}
    if not dpapi.available():
        return {"ok": False, "error": "dpapi_unavailable"}

    data = _load_plain()
    existed = provider in data
    if existed:
        del data[provider]
    _write_plain(data)
    return {"ok": True, "provider": provider, "set": False, "removed": existed}


def list_status(providers: Iterable[str] | None = None) -> Dict[str, Any]:
    names = [str(p).strip() for p in (providers or SUPPORTED_PROVIDERS) if str(p).strip()]
    if not dpapi.available():
        return {
            "ok": False,
            "enabled": False,
            "error": "dpapi_unavailable",
            "providers": [{"provider": p, "set": False, "last4": ""} for p in names],
        }

    try:
        plain = _load_plain()
    except Exception:
        plain = {}

    rows = []
    for provider in names:
        value = plain.get(provider, "")
        rows.append({"provider": provider, "set": bool(value), "last4": _last4(value)})
    return {"ok": True, "enabled": True, "providers": rows}

