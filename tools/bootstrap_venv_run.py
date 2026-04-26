# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
import site
import sys
from pathlib import Path

_DEPRECATED_HF_CACHE_VARS = (
    "TRANSFORMERS_CACHE",
    "PYTORCH_TRANSFORMERS_CACHE",
    "PYTORCH_PRETRAINED_BERT_CACHE",
)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _remove_foreign_site_packages(venv_site: Path) -> None:
    keep: list[str] = []
    venv_site_norm = _norm(str(venv_site))
    for item in sys.path:
        text = str(item or "").strip()
        if not text:
            keep.append(item)
            continue
        low = text.lower()
        if "site-packages" in low and _norm(text) != venv_site_norm:
            continue
        keep.append(item)
    sys.path[:] = keep


def _resolve_entry(root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (root / raw).resolve()
    return candidate


def _is_module_invocation(argv: list[str]) -> bool:
    return len(list(argv or [])) >= 2 and str((argv or [])[0]) == "-m" and bool(str((argv or [])[1]).strip())


def _normalize_hf_cache_env(root: Path, env: dict[str, str] | None = None) -> None:
    target = env if env is not None else os.environ
    hf_home = str((root / "data" / "cache" / "huggingface").resolve())
    target.setdefault("HF_HOME", hf_home)
    target.setdefault("HUGGINGFACE_HUB_CACHE", str((Path(target["HF_HOME"]) / "hub").resolve()))
    for name in _DEPRECATED_HF_CACHE_VARS:
        target.pop(name, None)
    try:
        Path(target["HF_HOME"]).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        Path(target["HUGGINGFACE_HUB_CACHE"]).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit("usage: bootstrap_venv_run.py <entry_script> [args...]")

    tools_dir = Path(__file__).resolve().parent
    root = tools_dir.parent
    venv_root = root / ".venv"
    venv_site = venv_root / "Lib" / "site-packages"

    os.chdir(root)
    os.environ.setdefault("PYTHONNOUSERSITE", "1")
    _normalize_hf_cache_env(root)
    if venv_root.exists():
        os.environ["VIRTUAL_ENV"] = str(venv_root)

    _remove_foreign_site_packages(venv_site)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if venv_site.exists():
        site.addsitedir(str(venv_site))
        _remove_foreign_site_packages(venv_site)

    if _is_module_invocation(argv):
        mod_name = str(argv[1]).strip()
        sys.argv = [mod_name] + list(argv[2:])
        runpy.run_module(mod_name, run_name="__main__")
        return 0

    entry = _resolve_entry(root, argv[0])
    if not entry.exists():
        raise SystemExit(f"entrypoint not found: {entry}")

    sys.argv = [str(entry)] + list(argv[1:])
    runpy.run_path(str(entry), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
