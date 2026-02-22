"""
modules/mem/passport.py

Legacy-compatible passport utilities for identity prompt and memory provenance.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from modules.state.identity_store import load_profile

logger = logging.getLogger(__name__)

PASSPORT_FLAGS: Dict[str, Any] = {
    "readonly": False,
    "storage_available": True,
    "log_available": True,
    "warnings": [],
}


def _runtime_warn(code: str, detail: str) -> None:
    msg = f"{code}: {detail}"
    PASSPORT_FLAGS["warnings"].append(msg)
    logger.warning(msg)


def _project_root() -> Path:
    env = str(os.getenv("ESTER_PROJECT_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    try:
        here = Path(__file__).resolve()
        return here.parents[2]
    except Exception:
        return Path.cwd()


PROJECT_ROOT = _project_root()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()


def _find_passport_path() -> Path:
    env_path = str(os.getenv("ESTER_PASSPORT_PATH") or "").strip()
    if env_path:
        return Path(env_path).expanduser()

    candidates = [
        PROJECT_ROOT / "data" / "passport" / "ester_identity.md",
        PROJECT_ROOT / "data" / "passport" / "passport.md",
        PROJECT_ROOT / "ester_identity.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


PASSPORT_MD_PATH = _find_passport_path()
LOG_DIR = STATE_DIR / "passport"
LOG_PATH = LOG_DIR / "passport_log.jsonl"

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception as exc:
    PASSPORT_FLAGS["readonly"] = True
    PASSPORT_FLAGS["log_available"] = False
    _runtime_warn("log_dir_unavailable", str(exc))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text_safe(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        return text if text.strip() else ""
    except FileNotFoundError:
        return ""
    except Exception as exc:
        _runtime_warn("passport_read_failed", f"{path}: {exc}")
        return ""


def _write_text_safe(path: Path, text: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return True
    except Exception as exc:
        PASSPORT_FLAGS["readonly"] = True
        PASSPORT_FLAGS["storage_available"] = False
        _runtime_warn("passport_write_failed", f"{path}: {exc}")
        return False


def _short_excerpt(text: str, max_chars: int = 5000) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def _sha256(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


def sha256_text(text: str) -> str:
    """Public helper used by older modules."""
    return _sha256(text)


def _append_log(entry: Dict[str, Any]) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        PASSPORT_FLAGS["log_available"] = False
        _runtime_warn("passport_log_append_failed", str(exc))


def _iter_log_reverse(limit: int) -> Iterable[Dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for line in reversed(lines[-max(1, int(limit)) :]):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except Exception:
            continue
    return out


@dataclasses.dataclass
class IdentityPassport:
    owner: str = "ester"
    source: str = "manual"
    version: int = 1
    created_at: str = dataclasses.field(default_factory=_now_iso)
    updated_at: str = dataclasses.field(default_factory=_now_iso)
    md_path: str = str(PASSPORT_MD_PATH)
    md_sha256: str = ""
    title: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def load_passport_markdown() -> str:
    return _read_text_safe(PASSPORT_MD_PATH)


def rewrite_identity_source(text: str) -> Dict[str, Any]:
    payload = str(text or "")
    if not payload.strip():
        return {"ok": False, "error": "empty_text"}
    ok = _write_text_safe(PASSPORT_MD_PATH, payload)
    return {"ok": ok, "path": str(PASSPORT_MD_PATH), "sha256": _sha256(payload)}


def build_identity_passport(owner: str = "ester", source: str = "manual", version: int = 1) -> IdentityPassport:
    raw = load_passport_markdown()
    lines = [ln.rstrip() for ln in raw.splitlines()]

    title = ""
    for line in lines:
        if not line.strip():
            continue
        title = line.lstrip("#").strip() if line.lstrip().startswith("#") else line.strip()
        break

    body_parts: List[str] = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        body_parts.append(text)
        if len(" ".join(body_parts)) > 2000:
            break
    summary_text = _short_excerpt(" ".join(body_parts), max_chars=1000)

    return IdentityPassport(
        owner=str(owner or "ester"),
        source=str(source or "manual"),
        version=int(version),
        created_at=_now_iso(),
        updated_at=_now_iso(),
        md_path=str(PASSPORT_MD_PATH),
        md_sha256=_sha256(raw) if raw else "",
        title=title,
        summary=summary_text,
    )


def make_passport(owner: str = "ester", source: str = "manual", version: int = 1) -> Dict[str, Any]:
    out = build_identity_passport(owner=owner, source=source, version=version).to_dict()
    out["runtime_flags"] = {
        "readonly": bool(PASSPORT_FLAGS.get("readonly")),
        "storage_available": bool(PASSPORT_FLAGS.get("storage_available")),
        "log_available": bool(PASSPORT_FLAGS.get("log_available")),
    }
    return out


def upsert_with_passport(
    mm: Any,
    text: str,
    meta: Optional[Dict[str, Any]] = None,
    source: str = "manual",
    version: int = 1,
) -> Dict[str, Any]:
    meta = dict(meta or {})
    owner = str(meta.get("owner") or "ester")

    passport = meta.get("passport")
    if not isinstance(passport, dict):
        passport = make_passport(owner=owner, source=source, version=version)
        meta["passport"] = passport

    entry = {
        "ts": _now_iso(),
        "owner": owner,
        "source": source,
        "text": str(text or ""),
        "meta": meta,
        "sha256": _sha256(str(text or "")),
    }

    saved = False
    if mm is not None:
        for method_name in ("append", "save", "upsert", "add"):
            fn = getattr(mm, method_name, None)
            if not callable(fn):
                continue
            try:
                try:
                    fn(text=str(text or ""), meta=meta)
                except TypeError:
                    fn(entry)
                saved = True
                break
            except Exception:
                continue

    _append_log(entry)
    return {"ok": True, "entry": entry, "saved": saved}


def list_recent(mm: Any, limit: int = 50) -> Dict[str, Any]:
    _ = mm
    return {"ok": True, "items": list(_iter_log_reverse(limit))}


def append(note: str, meta: Optional[Dict[str, Any]] = None, source: str = "manual://passport", version: int = 1) -> Dict[str, Any]:
    mm = None
    try:
        from services.mm_access import get_mm  # type: ignore

        mm = get_mm()
    except Exception as exc:
        _runtime_warn("mm_access_unavailable", str(exc))
    return upsert_with_passport(mm, str(note or ""), dict(meta or {}), source=str(source), version=int(version))


def runtime_status() -> Dict[str, Any]:
    return {
        "ok": True,
        "readonly": bool(PASSPORT_FLAGS.get("readonly")),
        "storage_available": bool(PASSPORT_FLAGS.get("storage_available")),
        "log_available": bool(PASSPORT_FLAGS.get("log_available")),
        "warnings": list(PASSPORT_FLAGS.get("warnings") or []),
        "path": str(PASSPORT_MD_PATH),
        "log_path": str(LOG_PATH),
    }


def _admin_name() -> str:
    profile = load_profile()
    return (
        str(profile.get("human_name") or "").strip()
        or str(os.getenv("ESTER_ADMIN_NAME") or "").strip()
        or str(os.getenv("ESTER_OWNER_NAME") or "").strip()
        or str(os.getenv("USERNAME") or "").strip()
        or "Owner"
    )


def _keywords() -> List[str]:
    env = str(os.getenv("ESTER_IDENTITY_KEYWORDS") or "").strip()
    if env:
        return [x.strip() for x in env.split(",") if x.strip()]
    name = _admin_name()
    return [name, "owner", "anchor", "sovereign"]


def get_identity_system_prompt(max_chars: int = 4000) -> str:
    """
    Return identity prompt text from passport markdown with a safe fallback.
    """
    raw = load_passport_markdown()
    if not raw:
        admin = _admin_name()
        return (
            "You are Ester, a digital assistant.\n"
            f"Owner profile name: {admin}.\n"
            "Use configured Web UI identity as the source of truth when available.\n"
            "No personal hardcoded data is allowed."
        )

    keys = [k.lower() for k in _keywords() if k]
    raw_l = raw.lower()
    if keys and not any(k in raw_l for k in keys):
        if str(os.getenv("ESTER_PASSPORT_AUTOFIX", "1")).strip() != "0":
            admin_line = _admin_name()
            addon = f"\n\n## Owner Profile\nOwner: {admin_line}\n"
            if _write_text_safe(PASSPORT_MD_PATH, raw + addon):
                raw = load_passport_markdown()

    excerpt = _short_excerpt(raw, max_chars=max_chars)
    return (
        "=== IDENTITY PASSPORT ===\n"
        f"{excerpt}\n"
        "========================="
    )


def get_identity_prompt(max_chars: int = 4000) -> str:
    """Compatibility alias."""
    return get_identity_system_prompt(max_chars=max_chars)
