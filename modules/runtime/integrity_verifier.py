# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

_LOCK = threading.RLock()

_VERIFY_CACHE: Dict[str, Any] | None = None
_VERIFY_CACHE_KEY = ""
_VERIFY_CACHE_TS_MONO = 0.0

_FAIL_STREAK = 0
_MODE_FORCED = ""
_LAST_ROLLBACK_REASON = ""

_BOOL_TRUE = {"1", "true", "yes", "on", "y"}


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    try:
        return max(min_value, int(os.getenv(name, str(default)) or default))
    except Exception:
        return max(min_value, int(default))


def _cache_ttl_sec() -> int:
    return _env_int("ESTER_INTEGRITY_TTL_SEC", 10, 1)


def _fail_max() -> int:
    return _env_int("ESTER_INTEGRITY_FAIL_MAX", 3, 1)


def _effective_slot() -> str:
    raw = _slot()
    with _LOCK:
        forced = str(_MODE_FORCED or "")
    if forced == "A":
        return "A"
    return raw


def _failure_snapshot(fail_max: int) -> Dict[str, Any]:
    with _LOCK:
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _note_success() -> None:
    global _FAIL_STREAK
    with _LOCK:
        if not _MODE_FORCED:
            _FAIL_STREAK = 0


def _note_failure(reason: str, fail_max: int) -> Dict[str, Any]:
    global _FAIL_STREAK, _MODE_FORCED, _LAST_ROLLBACK_REASON
    with _LOCK:
        _FAIL_STREAK = int(_FAIL_STREAK) + 1
        if _FAIL_STREAK >= int(fail_max):
            _MODE_FORCED = "A"
            _LAST_ROLLBACK_REASON = str(reason or "integrity_failure")
        return {
            "fail_streak": int(_FAIL_STREAK),
            "fail_max": int(fail_max),
            "mode_forced": str(_MODE_FORCED or ""),
            "last_rollback_reason": str(_LAST_ROLLBACK_REASON or ""),
        }


def _persist_dir() -> Path:
    root = str(os.getenv("PERSIST_DIR") or "").strip()
    if not root:
        root = str((Path.cwd() / "data").resolve())
    p = Path(root).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _integrity_root() -> Path:
    p = (_persist_dir() / "integrity").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cwd_integrity_root() -> Path:
    p = (Path.cwd() / "data" / "integrity").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _events_path() -> Path:
    return (_integrity_root() / "events.jsonl").resolve()


def _spec_guard_path() -> Path:
    return (_integrity_root() / "spec_guard.json").resolve()


def _manifest_path() -> Path:
    raw = str(os.getenv("ESTER_INTEGRITY_MANIFEST_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
    preferred = (_integrity_root() / "template_capability_SHA256SUMS.json").resolve()
    if preferred.exists():
        return preferred
    fallback = (_cwd_integrity_root() / "template_capability_SHA256SUMS.json").resolve()
    if fallback.exists():
        return fallback
    return preferred


def _clone(obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(obj, ensure_ascii=True))
    except Exception:
        return dict(obj)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        return
    except Exception:
        pass
    path.write_text(text, encoding="utf-8")


def _append_event(row: Dict[str, Any]) -> None:
    p = _events_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row or {}), ensure_ascii=True, separators=(",", ":"))
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _classify_scope(relpath: str) -> str:
    rp = str(relpath or "").replace("\\", "/").lower()
    if "capability" in rp:
        return "capabilities"
    if rp.endswith("/registry.py") and "/templates/" in rp:
        return "capabilities"
    return "templates"


def _protected_relpaths() -> List[str]:
    raw = str(os.getenv("ESTER_INTEGRITY_PROTECTED_RELPATHS") or "").strip()
    if raw:
        out: List[str] = []
        for part in raw.split(","):
            rp = str(part or "").strip().replace("\\", "/")
            if rp and rp not in out:
                out.append(rp)
        if out:
            return sorted(out)
    return sorted(
        [
            "modules/garage/agent_factory.py",
            "modules/garage/templates/pack_v1.py",
            "modules/garage/templates/registry.py",
        ]
    )


def _default_manifest_payload(path: Path) -> Dict[str, Any]:
    fail_max = _fail_max()
    raw_slot = _slot()
    eff_slot = _effective_slot()
    fail_state = _failure_snapshot(fail_max)
    return {
        "ok": False,
        "slot": eff_slot,
        "enforced": bool(eff_slot == "B"),
        "degraded": bool(eff_slot != raw_slot),
        "manifest_ok": False,
        "manifest_path": str(path),
        "manifest_root": "",
        "mismatch_count": 0,
        "mismatches": [],
        "missing": [],
        "extra": [],
        "last_mismatch": {},
        "last_verify_ts": int(time.time()),
        "last_error": "",
        "perf": {
            "cache_ttl_sec": int(_cache_ttl_sec()),
            "fail_streak": int(fail_state.get("fail_streak") or 0),
            "fail_max": int(fail_state.get("fail_max") or fail_max),
            "mode_forced": str(fail_state.get("mode_forced") or ""),
            "last_rollback_reason": str(fail_state.get("last_rollback_reason") or ""),
        },
    }


def _normalize_manifest_files(raw_files: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in list(raw_files or []):
        if not isinstance(row, dict):
            continue
        relpath = str(row.get("relpath") or "").strip().replace("\\", "/")
        sha = str(row.get("sha256") or "").strip().lower()
        if not relpath or len(sha) != 64:
            continue
        try:
            size = int(row.get("size") or 0)
        except Exception:
            size = 0
        out.append({"relpath": relpath, "sha256": sha, "size": max(0, size)})
    out.sort(key=lambda x: str(x.get("relpath") or ""))
    return out


def _manifest_digest(items: List[Dict[str, Any]]) -> str:
    src = "|".join(
        [
            f"{str(row.get('relpath') or '')}:{str(row.get('sha256') or '')}:{int(row.get('size') or 0)}"
            for row in list(items or [])
        ]
    )
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def _verify_manifest_uncached(path: Path) -> Dict[str, Any]:
    payload = _default_manifest_payload(path)
    fail_max = _fail_max()
    raw_slot = _slot()
    eff_slot = _effective_slot()
    now_ts = int(time.time())
    payload["last_verify_ts"] = now_ts

    try:
        if not path.exists():
            raise RuntimeError("manifest_missing")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("manifest_invalid")
        schema = str(raw.get("schema") or "")
        if schema != "ester.integrity.manifest.v1":
            raise RuntimeError("manifest_schema_invalid")

        root_raw = str(raw.get("root") or "").strip()
        root = Path(root_raw) if root_raw else Path.cwd()
        if not root.is_absolute():
            root = (Path.cwd() / root).resolve()
        root = root.resolve()

        files = _normalize_manifest_files(raw.get("files") or [])
        if not files:
            raise RuntimeError("manifest_files_empty")

        manifest_map = {str(row.get("relpath") or ""): dict(row) for row in files}
        mismatches: List[Dict[str, Any]] = []
        missing: List[str] = []
        extra: List[str] = []

        for relpath, row in manifest_map.items():
            expected_sha = str(row.get("sha256") or "").lower()
            expected_size = int(row.get("size") or 0)
            target = (root / relpath).resolve()
            if not target.exists() or (not target.is_file()):
                rec = {
                    "ts": now_ts,
                    "relpath": relpath,
                    "expected": expected_sha,
                    "actual": "",
                    "size_expected": expected_size,
                    "size_actual": 0,
                    "kind": "missing",
                    "scope": _classify_scope(relpath),
                }
                mismatches.append(rec)
                missing.append(relpath)
                continue
            actual_size = int(target.stat().st_size)
            actual_sha = _sha256_file(target).lower()
            if actual_sha != expected_sha or actual_size != expected_size:
                rec = {
                    "ts": now_ts,
                    "relpath": relpath,
                    "expected": expected_sha,
                    "actual": actual_sha,
                    "size_expected": expected_size,
                    "size_actual": actual_size,
                    "kind": ("sha256_mismatch" if actual_sha != expected_sha else "size_mismatch"),
                    "scope": _classify_scope(relpath),
                }
                mismatches.append(rec)

        for relpath in _protected_relpaths():
            if relpath not in manifest_map:
                rec = {
                    "ts": now_ts,
                    "relpath": relpath,
                    "expected": "",
                    "actual": "",
                    "size_expected": 0,
                    "size_actual": 0,
                    "kind": "missing_manifest_entry",
                    "scope": _classify_scope(relpath),
                }
                mismatches.append(rec)
                extra.append(relpath)

        manifest_ok = len(mismatches) == 0
        payload.update(
            {
                "ok": bool(manifest_ok),
                "manifest_ok": bool(manifest_ok),
                "manifest_root": str(root),
                "mismatch_count": len(mismatches),
                "mismatches": list(mismatches[:50]),
                "missing": sorted(set(missing))[:50],
                "extra": sorted(set(extra))[:50],
                "last_mismatch": (dict(mismatches[-1]) if mismatches else {}),
                "manifest_fingerprint": _manifest_digest(files),
                "last_error": "",
            }
        )
        if mismatches:
            for row in mismatches[:20]:
                _append_event(
                    {
                        "ts": now_ts,
                        "type": "INTEGRITY_MISMATCH",
                        "relpath": str(row.get("relpath") or ""),
                        "expected": str(row.get("expected") or ""),
                        "actual": str(row.get("actual") or ""),
                        "size_expected": int(row.get("size_expected") or 0),
                        "size_actual": int(row.get("size_actual") or 0),
                        "kind": str(row.get("kind") or ""),
                        "scope": str(row.get("scope") or ""),
                    }
                )
        if eff_slot == "B" and manifest_ok:
            _note_success()
    except Exception as exc:
        err = str(exc or "integrity_verify_error")
        payload["ok"] = False
        payload["manifest_ok"] = False
        payload["last_error"] = err
        if raw_slot == "B":
            fail_after = _note_failure("integrity_verify_error:" + err, fail_max)
            eff_after = _effective_slot()
            payload["slot"] = eff_after
            payload["enforced"] = bool(eff_after == "B")
            payload["degraded"] = bool(eff_after != raw_slot)
            payload["perf"]["mode_forced"] = str(fail_after.get("mode_forced") or "")
            payload["perf"]["last_rollback_reason"] = str(fail_after.get("last_rollback_reason") or "")
        _append_event(
            {
                "ts": now_ts,
                "type": "INTEGRITY_VERIFY_ERROR",
                "error": err,
            }
        )

    fail_state = _failure_snapshot(fail_max)
    payload["perf"]["fail_streak"] = int(fail_state.get("fail_streak") or 0)
    payload["perf"]["fail_max"] = int(fail_state.get("fail_max") or fail_max)
    payload["perf"]["mode_forced"] = str(fail_state.get("mode_forced") or "")
    payload["perf"]["last_rollback_reason"] = str(fail_state.get("last_rollback_reason") or "")
    return payload


def verify_manifest(manifest_path: str = "") -> Dict[str, Any]:
    global _VERIFY_CACHE, _VERIFY_CACHE_KEY, _VERIFY_CACHE_TS_MONO

    path = Path(manifest_path).resolve() if str(manifest_path).strip() else _manifest_path()
    ttl = _cache_ttl_sec()
    now_mono = time.monotonic()

    try:
        stat = path.stat()
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        size = int(stat.st_size)
    except Exception:
        mtime_ns = -1
        size = -1

    fail_state = _failure_snapshot(_fail_max())
    cache_key = "|".join(
        [
            str(path),
            str(mtime_ns),
            str(size),
            str(_slot()),
            str(_effective_slot()),
            str(fail_state.get("mode_forced") or ""),
        ]
    )

    with _LOCK:
        if (
            _VERIFY_CACHE is not None
            and _VERIFY_CACHE_KEY == cache_key
            and (now_mono - _VERIFY_CACHE_TS_MONO) <= float(ttl)
        ):
            return _clone(dict(_VERIFY_CACHE))

    payload = _verify_manifest_uncached(path)
    with _LOCK:
        _VERIFY_CACHE = _clone(payload)
        _VERIFY_CACHE_KEY = cache_key
        _VERIFY_CACHE_TS_MONO = now_mono
    return _clone(payload)


def _spec_guard_defaults() -> Dict[str, Any]:
    return {
        "schema": "ester.spec_guard.v1",
        "updated_ts": int(time.time()),
        "agents": {},
        "tamper_recent": 0,
        "last_tamper": {},
        "last_trusted_write": {},
    }


def _load_spec_guard() -> Dict[str, Any]:
    p = _spec_guard_path()
    if not p.exists():
        data = _spec_guard_defaults()
        _atomic_write_json(p, data)
        return data
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("spec_guard_invalid")
    except Exception:
        raw = _spec_guard_defaults()
    out = _spec_guard_defaults()
    out.update(raw)
    agents_raw = dict(out.get("agents") or {})
    agents: Dict[str, Dict[str, Any]] = {}
    for aid, row in agents_raw.items():
        key = str(aid or "").strip()
        if not key or (not isinstance(row, dict)):
            continue
        agents[key] = {
            "spec_sha256": str(row.get("spec_sha256") or ""),
            "spec_relpath": str(row.get("spec_relpath") or ""),
            "last_write_ts": max(0, int(row.get("last_write_ts") or 0)),
            "last_chain_id": str(row.get("last_chain_id") or ""),
            "last_reason": str(row.get("last_reason") or ""),
        }
    out["agents"] = agents
    out["updated_ts"] = max(0, int(out.get("updated_ts") or 0))
    out["tamper_recent"] = max(0, int(out.get("tamper_recent") or 0))
    out["last_tamper"] = dict(out.get("last_tamper") or {})
    out["last_trusted_write"] = dict(out.get("last_trusted_write") or {})
    return out


def _save_spec_guard(payload: Dict[str, Any]) -> None:
    src = _spec_guard_defaults()
    src.update(dict(payload or {}))
    _atomic_write_json(_spec_guard_path(), src)


def _spec_relpath(spec_path: Path) -> str:
    p = spec_path.resolve()
    try:
        return str(p.relative_to(_persist_dir())).replace("\\", "/")
    except Exception:
        try:
            return str(p.relative_to(Path.cwd())).replace("\\", "/")
        except Exception:
            return str(p).replace("\\", "/")


def _append_trusted_write_journal(
    *,
    agent_id: str,
    spec_relpath: str,
    prev_sha256: str,
    new_sha256: str,
    chain_id: str,
    reason: str,
    actor: str,
) -> None:
    try:
        from modules.volition import journal as volition_journal
    except Exception:
        return
    row = {
        "id": "vol_specwrite_" + hashlib.sha256(f"{agent_id}|{new_sha256}|{time.time_ns()}".encode("utf-8")).hexdigest()[:20],
        "ts": int(time.time()),
        "chain_id": str(chain_id or ""),
        "step": "agent.spec.write",
        "actor": str(actor or "ester"),
        "intent": "agent_spec_trusted_write",
        "action_kind": "agent.spec.write",
        "needs": ["agent.spec.write"],
        "allowed": True,
        "reason_code": "ALLOW",
        "reason": "trusted_spec_write",
        "slot": _slot(),
        "metadata": {
            "action_id": "agent.spec.write",
            "agent_id": str(agent_id or ""),
            "spec_relpath": str(spec_relpath or ""),
            "prev_sha256": str(prev_sha256 or ""),
            "new_sha256": str(new_sha256 or ""),
            "chain_id": str(chain_id or ""),
            "reason": str(reason or ""),
        },
        "action_id": "agent.spec.write",
        "decision": "allow",
        "policy_hit": "agent.spec.write",
        "duration_ms": 0,
    }
    try:
        volition_journal.append(row)
    except Exception:
        return


def trusted_spec_write(
    agent_id: str,
    spec_path: str,
    payload: Dict[str, Any],
    *,
    chain_id: str = "",
    reason: str = "",
    actor: str = "ester",
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    sp = Path(str(spec_path or "")).resolve()
    if not str(sp):
        return {"ok": False, "error": "spec_path_required", "error_code": "SPEC_PATH_REQUIRED"}
    sp.parent.mkdir(parents=True, exist_ok=True)
    prev_sha = _sha256_file(sp).lower() if sp.exists() and sp.is_file() else ""
    now_ts = int(time.time())

    try:
        text = json.dumps(dict(payload or {}), ensure_ascii=False, indent=2)
        tmp = sp.with_suffix(sp.suffix + ".tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(sp)
        except Exception:
            sp.write_text(text, encoding="utf-8")
        new_sha = _sha256_file(sp).lower()
    except Exception as exc:
        return {"ok": False, "error": "spec_write_failed", "error_code": "SPEC_WRITE_FAILED", "detail": str(exc)}

    guard = _load_spec_guard()
    agents = dict(guard.get("agents") or {})
    relpath = _spec_relpath(sp)
    agents[aid] = {
        "spec_sha256": str(new_sha),
        "spec_relpath": str(relpath),
        "last_write_ts": int(now_ts),
        "last_chain_id": str(chain_id or ""),
        "last_reason": str(reason or ""),
    }
    guard["agents"] = agents
    guard["updated_ts"] = int(now_ts)
    guard["last_trusted_write"] = {
        "ts": int(now_ts),
        "agent_id": aid,
        "chain_id": str(chain_id or ""),
        "spec_relpath": str(relpath),
        "prev_sha256": str(prev_sha or ""),
        "new_sha256": str(new_sha),
        "reason": str(reason or ""),
    }
    _save_spec_guard(guard)
    _append_event(
        {
            "ts": now_ts,
            "type": "SPEC_TRUSTED_WRITE",
            "agent_id": aid,
            "spec_relpath": str(relpath),
            "prev_sha256": str(prev_sha or ""),
            "new_sha256": str(new_sha),
            "chain_id": str(chain_id or ""),
            "reason": str(reason or ""),
        }
    )
    _append_trusted_write_journal(
        agent_id=aid,
        spec_relpath=str(relpath),
        prev_sha256=str(prev_sha or ""),
        new_sha256=str(new_sha),
        chain_id=str(chain_id or ""),
        reason=str(reason or ""),
        actor=str(actor or "ester"),
    )
    return {
        "ok": True,
        "agent_id": aid,
        "spec_path": str(sp),
        "spec_relpath": str(relpath),
        "prev_sha256": str(prev_sha or ""),
        "new_sha256": str(new_sha),
        "ts": int(now_ts),
    }


def check_spec_tamper(agent_id: str, spec_path: str) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return {"ok": False, "tamper": True, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}
    sp = Path(str(spec_path or "")).resolve()
    relpath = _spec_relpath(sp)
    guard = _load_spec_guard()
    agents = dict(guard.get("agents") or {})
    row = dict(agents.get(aid) or {})
    expected = str(row.get("spec_sha256") or "").strip().lower()
    actual = _sha256_file(sp).lower() if sp.exists() and sp.is_file() else ""
    tamper = (not expected) or (not actual) or (expected != actual)
    if not tamper:
        return {
            "ok": True,
            "tamper": False,
            "agent_id": aid,
            "spec_relpath": str(relpath),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "error_code": "",
            "error": "",
        }

    now_ts = int(time.time())
    guard["tamper_recent"] = max(0, int(guard.get("tamper_recent") or 0)) + 1
    guard["updated_ts"] = int(now_ts)
    guard["last_tamper"] = {
        "ts": int(now_ts),
        "agent_id": aid,
        "spec_relpath": str(relpath),
        "expected": str(expected or ""),
        "actual": str(actual or ""),
    }
    _save_spec_guard(guard)
    _append_event(
        {
            "ts": now_ts,
            "type": "SPEC_TAMPER",
            "agent_id": aid,
            "spec_relpath": str(relpath),
            "expected": str(expected or ""),
            "actual": str(actual or ""),
        }
    )
    return {
        "ok": False,
        "tamper": True,
        "agent_id": aid,
        "spec_relpath": str(relpath),
        "expected_sha256": str(expected or ""),
        "actual_sha256": str(actual or ""),
        "error_code": "SPEC_TAMPER_NO_JOURNAL",
        "error": "spec_tamper_no_journal",
    }


def _reason_code_for_manifest(rep: Dict[str, Any]) -> str:
    if int(rep.get("mismatch_count") or 0) <= 0:
        return "INTEGRITY_UNAVAILABLE"
    mm = dict((rep.get("mismatches") or [{}])[0] or {})
    scope = str(mm.get("scope") or "")
    if scope == "capabilities":
        return "CAP_MATRIX_TAMPER"
    return "TEMPLATE_TAMPER"


def _should_enforce_slot_b() -> bool:
    return bool(_effective_slot() == "B")


def _set_quarantine(
    *,
    agent_id: str,
    reason_code: str,
    kind: str,
    source: str,
    template_id: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from modules.runtime import drift_quarantine
    except Exception:
        return {}
    try:
        rep = drift_quarantine.set_manual_quarantine(
            agent_id,
            reason_code=str(reason_code or ""),
            severity="HIGH",
            kind=str(kind or "integrity_tamper"),
            source=str(source or "integrity.guard"),
            template_id=str(template_id or ""),
            details=dict(details or {}),
        )
        if isinstance(rep, dict):
            return rep
    except Exception:
        return {}
    return {}


def precheck_create(template_id: str = "", *, action: str = "agent.create") -> Dict[str, Any]:
    rep = verify_manifest()
    out = {
        "ok": True,
        "error_code": "",
        "error": "",
        "reason_code": "",
        "slot": str(rep.get("slot") or _effective_slot()),
        "enforced": bool(rep.get("enforced")),
        "degraded": bool(rep.get("degraded")),
        "action": str(action or "agent.create"),
        "template_id": str(template_id or ""),
        "integrity": {
            "manifest_ok": bool(rep.get("manifest_ok")),
            "mismatch_count": int(rep.get("mismatch_count") or 0),
            "last_error": str(rep.get("last_error") or ""),
            "last_mismatch": dict(rep.get("last_mismatch") or {}),
            "last_verify_ts": int(rep.get("last_verify_ts") or 0),
        },
    }
    if bool(rep.get("manifest_ok")):
        return out
    if bool(rep.get("enforced")):
        reason_code = _reason_code_for_manifest(rep)
        out["ok"] = False
        out["reason_code"] = str(reason_code)
        if reason_code == "INTEGRITY_UNAVAILABLE":
            out["error_code"] = "INTEGRITY_UNAVAILABLE"
            out["error"] = "integrity_unavailable"
        else:
            out["error_code"] = "INTEGRITY_TAMPER"
            out["error"] = "integrity_tamper"
    else:
        out["warnings"] = ["integrity_manifest_mismatch_observe_only"]
    return out


def precheck_agent_action(
    agent_id: str,
    *,
    template_id: str = "",
    spec_path: str = "",
    action: str,
) -> Dict[str, Any]:
    aid = str(agent_id or "").strip()
    act = str(action or "").strip() or "agent.action"
    if not aid:
        return {"ok": False, "error": "agent_id_required", "error_code": "AGENT_ID_REQUIRED"}

    manifest = verify_manifest()
    out = {
        "ok": True,
        "error_code": "",
        "error": "",
        "reason_code": "",
        "slot": str(manifest.get("slot") or _effective_slot()),
        "enforced": bool(manifest.get("enforced")),
        "degraded": bool(manifest.get("degraded")),
        "action": act,
        "agent_id": aid,
        "template_id": str(template_id or ""),
        "integrity": {
            "manifest_ok": bool(manifest.get("manifest_ok")),
            "mismatch_count": int(manifest.get("mismatch_count") or 0),
            "last_error": str(manifest.get("last_error") or ""),
            "last_mismatch": dict(manifest.get("last_mismatch") or {}),
            "last_verify_ts": int(manifest.get("last_verify_ts") or 0),
        },
        "spec_guard": {},
    }

    warnings: List[str] = []
    if not bool(manifest.get("manifest_ok")):
        if bool(manifest.get("enforced")):
            reason_code = _reason_code_for_manifest(manifest)
            out["ok"] = False
            out["reason_code"] = str(reason_code)
            if reason_code == "INTEGRITY_UNAVAILABLE":
                out["error_code"] = "INTEGRITY_UNAVAILABLE"
                out["error"] = "integrity_unavailable"
            else:
                out["error_code"] = "INTEGRITY_TAMPER"
                out["error"] = "integrity_tamper"
                out["quarantine"] = _set_quarantine(
                    agent_id=aid,
                    reason_code=str(reason_code),
                    kind="integrity_tamper",
                    source=act,
                    template_id=str(template_id or ""),
                    details={"manifest": dict(out.get("integrity") or {})},
                )
            return out
        warnings.append("integrity_manifest_mismatch_observe_only")

    if str(spec_path or "").strip():
        spec_rep = check_spec_tamper(aid, spec_path)
        out["spec_guard"] = {
            "tamper": bool(spec_rep.get("tamper")),
            "spec_relpath": str(spec_rep.get("spec_relpath") or ""),
            "expected_sha256": str(spec_rep.get("expected_sha256") or ""),
            "actual_sha256": str(spec_rep.get("actual_sha256") or ""),
        }
        if bool(spec_rep.get("tamper")):
            if _should_enforce_slot_b():
                out["ok"] = False
                out["error_code"] = "SPEC_TAMPER_NO_JOURNAL"
                out["error"] = "spec_tamper_no_journal"
                out["reason_code"] = "SPEC_TAMPER_NO_JOURNAL"
                out["quarantine"] = _set_quarantine(
                    agent_id=aid,
                    reason_code="SPEC_TAMPER_NO_JOURNAL",
                    kind="spec_tamper",
                    source=act,
                    template_id=str(template_id or ""),
                    details={
                        "spec_relpath": str(spec_rep.get("spec_relpath") or ""),
                        "expected": str(spec_rep.get("expected_sha256") or ""),
                        "actual": str(spec_rep.get("actual_sha256") or ""),
                    },
                )
                return out
            warnings.append("spec_tamper_observe_only")

    if warnings:
        out["warnings"] = list(warnings)
    return out


def build_integrity_status() -> Dict[str, Any]:
    rep = verify_manifest()
    guard = _load_spec_guard()
    agents = dict(guard.get("agents") or {})
    return {
        "ok": bool(rep.get("manifest_ok")),
        "slot": str(rep.get("slot") or _effective_slot()),
        "enforced": bool(rep.get("enforced")),
        "degraded": bool(rep.get("degraded")),
        "manifest_ok": bool(rep.get("manifest_ok")),
        "mismatch_count": int(rep.get("mismatch_count") or 0),
        "last_mismatch": dict(rep.get("last_mismatch") or {}),
        "last_verify_ts": int(rep.get("last_verify_ts") or 0),
        "last_error": str(rep.get("last_error") or ""),
        "spec_guard": {
            "tracked_agents": len(agents),
            "tamper_recent": int(guard.get("tamper_recent") or 0),
            "last_tamper": dict(guard.get("last_tamper") or {}),
            "last_trusted_write": dict(guard.get("last_trusted_write") or {}),
        },
        "perf": dict(rep.get("perf") or {}),
    }


__all__ = [
    "verify_manifest",
    "trusted_spec_write",
    "check_spec_tamper",
    "precheck_create",
    "precheck_agent_action",
    "build_integrity_status",
]

