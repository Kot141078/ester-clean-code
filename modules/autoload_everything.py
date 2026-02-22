"""Autoload (import) a bunch of modules/packages so that decorators/registries run.

def _skip_autoload_name(name: str) -> bool:
    n = (name or '').lower()
    if '__disabled__' in n:
        return True
    if 'chat_api b' in n:
        return True
    if ' ' in n:
        return True
    return False


Goal:
- reduce “it works only after first call” bugs
- make startup deterministic
- never crash the app: best-effort, with a report

Usage:
    from modules.autoload_everything import autoload_everything
    report = autoload_everything()
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

LOG = logging.getLogger(__name__)


DEFAULT_PACKAGES: List[str] = [
    "routes",
    "modules",
    "skills",
    "providers",
    "bridges",
]

# Things that are known to have heavy side-effects / long imports / duplicate register logic.
DEFAULT_SKIP_PREFIXES: Tuple[str, ...] = (
    "modules.register_all",
    "routes.register_all",
)


@dataclass
class AutoloadItem:
    name: str
    ok: bool
    error: Optional[str] = None


def safe_import(module_name: str) -> AutoloadItem:
    try:
        importlib.import_module(module_name)
        return AutoloadItem(name=module_name, ok=True)
    except Exception as e:
        return AutoloadItem(name=module_name, ok=False, error=str(e))


def iter_modules(package_name: str) -> Iterable[str]:
    """Yield full module names under a package."""
    pkg = None
    try:
        pkg = importlib.import_module(package_name)
    except Exception:
        return

    if not hasattr(pkg, "__path__"):
        return

    for modinfo in pkgutil.walk_packages(pkg.__path__, package_name + "."):
        yield modinfo.name


def autoload_everything(
    packages: Optional[List[str]] = None,
    skip_prefixes: Optional[Tuple[str, ...]] = None,
    verbose: bool = False,
) -> Dict[str, List[AutoloadItem]]:
    packages = packages or list(DEFAULT_PACKAGES)
    skip_prefixes = skip_prefixes or DEFAULT_SKIP_PREFIXES

    report: Dict[str, List[AutoloadItem]] = {}
    seen: Set[str] = set()

    for pkg in packages:
        items: List[AutoloadItem] = []
        for modname in iter_modules(pkg):
            if modname in seen:
                continue
            if _skip_autoload_name(modname):
                continue
            if any(modname.startswith(pfx) for pfx in skip_prefixes):
                continue
            seen.add(modname)
            item = safe_import(modname)
            items.append(item)
            if verbose:
                if item.ok:
                    LOG.info("[autoload] OK: %s", modname)
                else:
                    LOG.warning("[autoload] FAIL: %s (%s)", modname, item.error)
        report[pkg] = items

    return report


def autoload_modules(
    app: Optional[object] = None,
    mode: str = "allowlist",
    allowlist_path: str = "modules/autoload_allowlist.txt",
    max_failures: int = 50,
    log_each: bool = True,
) -> Dict[str, List[AutoloadItem]]:
    """
    Compatibility wrapper for run_ester_fixed:
      autoload_modules(app=..., mode=allowlist, allowlist_path=..., max_failures=..., log_each=...)
    """
    mode = (mode or "allowlist").lower()
    report: Dict[str, List[AutoloadItem]] = {"ok": [], "fail": []}

    def _log(item: AutoloadItem) -> None:
        if not log_each:
            return
        if item.ok:
            LOG.info("[autoload] ok: %s", item.name)
        else:
            LOG.warning("[autoload] fail: %s -> %s", item.name, item.error)

    if mode == "allowlist":
        try:
            with open(allowlist_path, "r", encoding="utf-8") as f:
                mods = [ln.strip() for ln in f.readlines() if ln.strip() and not ln.strip().startswith("#")]
        except Exception as e:
            LOG.warning("[autoload] allowlist read failed: %s", e)
            mods = []

        failures = 0
        for m in mods:
            it = safe_import(m)
            _log(it)
            report["ok" if it.ok else "fail"].append(it)
            if not it.ok:
                failures += 1
                if failures >= max_failures:
                    LOG.warning("[autoload] max_failures reached: %s", max_failures)
                    break
        return report

    # Fallback: full autoload
    rep = autoload_everything(verbose=log_each)
    return rep
