"""
autoload_everything.py — best-effort loader

Goal:
- Discover modules automatically (no manual allowlist pain).
- Import everything that can be imported.
- Activate only Flask-like hooks: register(app) / init_app(app) / setup(app)
  (with signature guard so we don't call unrelated register(kind, ...))
- Quarantine modules that fail, and write a JSON report.

Usage expectation:
- register_all (or app bootstrap) calls autoload_modules(...).
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import pkgutil
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


_HOOK_NAMES = ("register", "init_app", "setup")

# Modules that must NOT be auto-imported in "load all" mode because they are bootstrap/aggregators
# and can create duplicate registrations or side-effects.
_DEFAULT_SKIP: Tuple[str, ...] = (
    "modules.autoload_everything",
    "modules.register_all",
)

LOG = logging.getLogger("autoload_everything")


@dataclass
class Failure:
    module: str
    where: str
    error: str
    traceback: str


def _read_text_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8", errors="replace")
    out: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        # If the file is corrupted, do not crash startup.
        return {}


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _utc_iso() -> str:
    # No datetime import to keep it tiny; good enough for logs.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _discover_modules(package: str) -> List[str]:
    """
    Returns full import names like: modules.foo, modules.bar.baz
    """
    pkg = importlib.import_module(package)
    names: List[str] = []
    # walk_packages yields ModuleInfo(name=..., ispkg=...)
    for mi in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        names.append(mi.name)
    # stable & unique
    return sorted(set(names))


def _looks_like_flask_app_param(p: inspect.Parameter) -> bool:
    if p.name in ("app", "application"):
        return True
    ann = p.annotation
    if ann is inspect._empty:
        return False
    # Be tolerant: some code uses forward refs / strings
    s = str(ann)
    return "Flask" in s or "flask" in s


def _is_app_hook(fn: Callable) -> bool:
    """
    We only want to call hooks like register(app) / init_app(app) / setup(app).
    Avoid calling random register(kind, ...) functions.
    """
    try:
        sig = inspect.signature(fn)
    except Exception:
        return False

    params = list(sig.parameters.values())
    if not params:
        return False

    # allow: register(app), register(app, ...optional...), register(app, *args, **kwargs)
    first = params[0]
    if first.kind not in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        return False

    if not _looks_like_flask_app_param(first):
        return False

    # ensure no other REQUIRED params besides first
    for p in params[1:]:
        if p.default is inspect._empty and p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return False

    return True


def _pick_hook(mod: Any) -> Optional[Callable]:
    for name in _HOOK_NAMES:
        fn = getattr(mod, name, None)
        if callable(fn) and _is_app_hook(fn):
            return fn
    return None


def autoload_modules(
    app: Any = None,
    mode: str = "all",
    allowlist_path: str = "modules/autoload_allowlist.txt",
    package: str = "modules",
    log_each: bool = True,
    max_failures: int = 50,
    skip: Optional[List[str]] = None,
    quarantine_path: str = "modules/autoload_quarantine.json",
    retry_quarantined: bool = False,
    report_dir: str = "logs/autoload",
    **_ignored_kwargs: Any,
) -> Dict[str, Any]:
    """
    mode:
      - "allowlist": import only modules listed in allowlist_path
      - "all": discover everything under package

    quarantine:
      - failing modules are written into quarantine_path
      - in next runs, they are skipped unless retry_quarantined=True

    Returns dict:
      activated: int
      failed: int
      failures: list[(module, error)]
      activated_modules: list[str]
      seconds: float
      report_path: str (if report written)
    """
    t0 = time.time()
    failures: List[Failure] = []
    activated: List[str] = []
    imported_nohook: List[str] = []
    skipped: List[str] = []

    skip_set = set(_DEFAULT_SKIP)
    if skip:
        skip_set.update(skip)

    # Load quarantine
    qpath = Path(quarantine_path)
    quarantine = _load_json(qpath)
    broken: Dict[str, Any] = quarantine.get("broken", {}) if isinstance(quarantine, dict) else {}
    broken = broken if isinstance(broken, dict) else {}

    if mode == "allowlist":
        targets = _read_text_lines(Path(allowlist_path))
        # Normalize to full names if user gave short ones
        norm: List[str] = []
        for t in targets:
            if t.startswith(package + "."):
                norm.append(t)
            else:
                norm.append(package + "." + t.lstrip("."))
        targets = norm
    else:
        targets = _discover_modules(package)

    # Filter targets
    filtered: List[str] = []
    for name in targets:
        if name in skip_set:
            skipped.append(name)
            continue
        # skip private-ish modules
        tail = name.split(".")[-1]
        if tail.startswith("_"):
            skipped.append(name)
            continue
        if (name in broken) and (not retry_quarantined):
            skipped.append(name)
            continue
        filtered.append(name)

    failed_count = 0

    for name in filtered:
        try:
            mod = importlib.import_module(name)
            hook = _pick_hook(mod)

            if hook and app is not None:
                try:
                    hook(app)
                    activated.append(name)
                    if log_each:
                        LOG.info(f"[autoload] activated: {name}")
                except Exception as e:
                    # Some hook failures are “duplicate registration” noise; treat as warning, not fatal.
                    msg = str(e)
                    tb = traceback.format_exc()
                    # Typical Flask blueprint duplicate:
                    # ValueError: The name 'xxx' is already registered for this blueprint. Use 'name=' to...
                    if "already registered" in msg or "is already registered" in msg:
                        activated.append(name)
                        if log_each:
                            LOG.warning(f"[autoload] activated-with-warning (duplicate): {name} :: {msg}")
                    else:
                        failed_count += 1
                        failures.append(Failure(module=name, where="hook", error=msg, traceback=tb))
                        if log_each:
                            LOG.warning(f"[autoload] FAILED(hook): {name} :: {msg}")
            else:
                imported_nohook.append(name)
                if log_each:
                    LOG.info(f"[autoload] imported (no hook): {name}")

        except Exception as e:
            failed_count += 1
            msg = str(e)
            tb = traceback.format_exc()
            failures.append(Failure(module=name, where="import", error=msg, traceback=tb))
            if log_each:
                LOG.warning(f"[autoload] FAILED(import): {name} :: {msg}")

        if failed_count >= max_failures:
            LOG.warning(f"[autoload] stopping early: reached max_failures={max_failures}")
            break

    # Update quarantine
    now = _utc_iso()
    new_broken: Dict[str, Any] = dict(broken)

    for f in failures:
        prev = new_broken.get(f.module) if isinstance(new_broken.get(f.module), dict) else {}
        cnt = int(prev.get("count", 0)) if isinstance(prev, dict) else 0
        first_seen = prev.get("first_seen_utc", now) if isinstance(prev, dict) else now
        new_broken[f.module] = {
            "first_seen_utc": first_seen,
            "last_seen_utc": now,
            "count": cnt + 1,
            "where": f.where,
            "error": f.error[:500],
        }

    quarantine_payload = {
        "schema": 1,
        "updated_utc": now,
        "broken": new_broken,
        "last_run": {
            "mode": mode,
            "activated": activated,
            "imported_nohook": imported_nohook[:200],
            "skipped": skipped[:200],
            "failed": [(f.module, f.error[:300]) for f in failures[:100]],
            "seconds": round(time.time() - t0, 3),
        },
    }
    _save_json(qpath, quarantine_payload)

    # Write report (full tracebacks, to file)
    rdir = Path(report_dir)
    rdir.mkdir(parents=True, exist_ok=True)
    report_path = rdir / f"autoload_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_payload = {
        "schema": 1,
        "created_utc": now,
        "mode": mode,
        "activated": activated,
        "imported_nohook": imported_nohook,
        "skipped": skipped,
        "failures": [
            {
                "module": f.module,
                "where": f.where,
                "error": f.error,
                "traceback": f.traceback,
            }
            for f in failures
        ],
        "seconds": round(time.time() - t0, 3),
    }
    _save_json(report_path, report_payload)

    return {
        "activated": len(activated),
        "failed": failed_count,
        "failures": [(f.module, f.error) for f in failures[:25]],
        "activated_modules": activated,
        "seconds": round(time.time() - t0, 3),
        "report_path": str(report_path),
        "quarantine_path": str(qpath),
        "skipped": skipped[:50],
    }