# -*- coding: utf-8 -*-
from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

DEFAULT_INCLUDE_ROOTS: Tuple[str, ...] = (
    "modules",
    "routes",
    "templates",
    "tools",
    "tests",
    "docs",
    "security",
    "bridges",
    "scripts",
    "schemas",
    "config",
)

DEFAULT_EXCLUDE_DIRS: Tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
)

DEFAULT_EXCLUDE_GLOBS: Tuple[str, ...] = (
    ".env",
    ".env.*",
    "**/*.pem",
    "**/*.key",
    "**/*secret*",
    "**/*token*",
    "data/passport/**",
    "data/memory/**",
    "state/vault/**",
    "state/identity/**",
    "state/settings/**",
)

KEY_LIKE_FILENAME_RE = re.compile(
    r"(secret|token|api[_-]?key|password|passwd|credential|private[_-]?key)", re.IGNORECASE
)


@dataclass(frozen=True)
class DumpPolicy:
    project_root: Path
    include_roots: Tuple[str, ...]
    exclude_dirs: Tuple[str, ...]
    exclude_globs: Tuple[str, ...]
    include_data: bool = False
    include_dotenv: bool = False
    state_dir_rel: str = ""

    def should_include(self, relpath: str) -> Tuple[bool, str]:
        rel = _norm_rel(relpath)
        if not rel:
            return False, "empty_path"

        if not _in_include_roots(rel, self.include_roots):
            return False, "outside_include_roots"

        name = rel.rsplit("/", 1)[-1]

        if not self.include_dotenv and _is_dotenv_name(name):
            return False, "dotenv_blocked"

        if self.state_dir_rel and (rel == self.state_dir_rel or rel.startswith(self.state_dir_rel + "/")):
            return False, "state_dir_blocked"

        for pattern in self.exclude_globs:
            if _glob_match(rel, pattern):
                return False, f"glob:{pattern}"

        if KEY_LIKE_FILENAME_RE.search(name):
            return False, "key_like_filename"

        return True, "included"


def build_policy(
    project_root: str | Path,
    *,
    include_data: bool = False,
    include_dotenv: bool = False,
) -> DumpPolicy:
    root = Path(project_root).resolve()
    include_roots: List[str] = [
        _norm_rel(p) for p in DEFAULT_INCLUDE_ROOTS if (root / p).exists()
    ]
    if include_data and (root / "data").exists() and "data" not in include_roots:
        include_roots.append("data")

    state_dir_rel = ""
    state_dir_abs = resolve_state_dir(root)
    try:
        state_dir_rel = _norm_rel(state_dir_abs.resolve().relative_to(root.resolve()).as_posix())
    except Exception:
        state_dir_rel = ""

    return DumpPolicy(
        project_root=root,
        include_roots=tuple(sorted(set(include_roots))),
        exclude_dirs=DEFAULT_EXCLUDE_DIRS,
        exclude_globs=DEFAULT_EXCLUDE_GLOBS,
        include_data=bool(include_data),
        include_dotenv=bool(include_dotenv),
        state_dir_rel=state_dir_rel,
    )


def iter_policy_roots(policy: DumpPolicy) -> Iterable[Path]:
    for relroot in policy.include_roots:
        root = (policy.project_root / relroot).resolve()
        if root.exists() and root.is_dir():
            yield root


def resolve_state_dir(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    env_value = str(os.getenv("ESTER_STATE_DIR", "") or "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()

    if os.name == "nt":
        local_app_data = str(os.getenv("LOCALAPPDATA", "") or "").strip()
        if local_app_data:
            return (Path(local_app_data) / "Ester" / "state").resolve()
        return (Path.home() / "AppData" / "Local" / "Ester" / "state").resolve()

    return (Path.home() / ".local" / "share" / "ester" / "state").resolve()


def _is_dotenv_name(name: str) -> bool:
    lower = str(name or "").lower()
    return lower == ".env" or lower.startswith(".env.")


def _glob_match(rel: str, pattern: str) -> bool:
    rel_l = rel.lower()
    pat_l = str(pattern or "").strip().lower()

    if fnmatch.fnmatch(rel_l, pat_l):
        return True

    if pat_l.startswith("**/"):
        short = pat_l[3:]
        if fnmatch.fnmatch(rel_l, short):
            return True

    return False


def _in_include_roots(rel: str, include_roots: Sequence[str]) -> bool:
    rel_l = rel.lower()
    for root in include_roots:
        base = _norm_rel(root).lower()
        if not base:
            continue
        if rel_l == base or rel_l.startswith(base + "/"):
            return True
    return False


def _norm_rel(path: str) -> str:
    raw = str(path or "").replace("\\", "/").strip()
    while raw.startswith("./"):
        raw = raw[2:]
    return raw.strip("/")


__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_EXCLUDE_GLOBS",
    "DEFAULT_INCLUDE_ROOTS",
    "DumpPolicy",
    "build_policy",
    "iter_policy_roots",
    "resolve_state_dir",
]
