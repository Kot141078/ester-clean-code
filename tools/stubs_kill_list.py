# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


TODO_RE = re.compile(r"\b(TODO|FIXME|STUB|PLACEHOLDER)\b", re.IGNORECASE)

STUB_BASE_SCORE: Dict[str, int] = {
    "pass_only": 72,
    "ellipsis": 74,
    "not_implemented": 90,
    "placeholder_return": 63,
    "todo_marker": 45,
    "suppress_init": 80,
}

REASON_PRIORITY: Dict[str, int] = {
    "unknown": 0,
    "import_only": 1,
    "template": 2,
    "action": 3,
    "route": 4,
    "entry": 5,
}


@dataclass
class StubCandidate:
    path: str
    module: str
    symbol: str
    stub_kind: str
    line_start: int
    line_end: int
    excerpt: str
    marker: str = ""


@dataclass
class ModuleInfo:
    path: Path
    rel_path: str
    module: str
    imports: Set[str]
    names: Set[str]
    stub_candidates: List[StubCandidate]


def _as_posix(path: Path) -> str:
    return path.as_posix()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _iter_py_files(root: Path) -> List[Path]:
    return sorted([p for p in root.rglob("*.py") if p.is_file()], key=lambda p: _as_posix(p))


def _module_from_file(path: Path, base: Path, package_root: str) -> str:
    rel = path.relative_to(base)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    parts = [p for p in parts if p]
    if not parts:
        return package_root
    return package_root + "." + ".".join(parts)


def _resolve_import(current_module: str, mod: Optional[str], level: int) -> str:
    module = str(mod or "").strip()
    if level <= 0:
        return module
    if not current_module:
        return module
    pkg_parts = current_module.split(".")[:-1]
    up = max(0, level - 1)
    if up > len(pkg_parts):
        pkg_parts = []
    else:
        pkg_parts = pkg_parts[: len(pkg_parts) - up]
    if module:
        pkg_parts.extend(module.split("."))
    return ".".join([p for p in pkg_parts if p])


def _path_excerpt(lines: List[str], start: int, end: int) -> str:
    s = max(1, int(start))
    e = max(s, int(end))
    out: List[str] = []
    for idx in range(s, min(e, s + 1) + 1):
        if 1 <= idx <= len(lines):
            txt = lines[idx - 1].strip()
            if txt:
                out.append(txt)
    return " | ".join(out)[:220]


def _set_parent_map(tree: ast.AST) -> Dict[ast.AST, ast.AST]:
    out: Dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            out[child] = parent
    return out


def _literal_str_set(node: ast.AST) -> Set[str]:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return set()
    out: Set[str] = set()
    if isinstance(value, (list, tuple, set)):
        for x in value:
            if isinstance(x, str) and x.strip():
                out.add(x.strip())
    return out


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _strip_docstring_body(body: Sequence[ast.stmt]) -> List[ast.stmt]:
    rows = list(body)
    if rows and _is_docstring_stmt(rows[0]):
        return rows[1:]
    return rows


def _is_ellipsis_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    )


def _is_raise_not_implemented(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Raise) or stmt.exc is None:
        return False
    exc = stmt.exc
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    if isinstance(exc, ast.Call):
        fn = exc.func
        if isinstance(fn, ast.Name):
            if fn.id == "NotImplementedError":
                return True
            if fn.id == "RuntimeError":
                if exc.args and isinstance(exc.args[0], ast.Constant) and isinstance(exc.args[0].value, str):
                    return bool(TODO_RE.search(str(exc.args[0].value)))
        if isinstance(fn, ast.Attribute):
            return fn.attr == "NotImplementedError"
    return False


def _is_ok_true_dict(node: ast.AST) -> bool:
    if not isinstance(node, ast.Dict):
        return False
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == "ok":
            if isinstance(v, ast.Constant) and v.value in (True, 1):
                return True
    return False


def _has_return_none(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return):
            if sub.value is None:
                return True
            if isinstance(sub.value, ast.Constant) and sub.value.value is None:
                return True
    return False


def _has_ok_dict_return(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and sub.value is not None and _is_ok_true_dict(sub.value):
            return True
    return False


def _function_symbol(node: ast.AST, parents: Dict[ast.AST, ast.AST]) -> str:
    parts: List[str] = []
    cur: Optional[ast.AST] = node
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parts.append(cur.name)
        cur = parents.get(cur)
    return ".".join(reversed(parts))


def _module_imports_and_names(tree: ast.AST, module_name: str) -> Tuple[Set[str], Set[str], Set[str]]:
    imports: Set[str] = set()
    names: Set[str] = set()
    exports: Set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                nm = str(a.name or "").strip()
                if nm:
                    imports.add(nm)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import(module_name, node.module, int(node.level or 0))
            if base:
                imports.add(base)
            for a in node.names:
                an = str(a.name or "").strip()
                if an and an != "*" and base:
                    imports.add(base + "." + an)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    exports.update(_literal_str_set(node.value))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__" and node.value is not None:
                exports.update(_literal_str_set(node.value))

        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return imports, names, exports


def _module_level_suppress_init(tree: ast.AST, lines: List[str], rel_path: str, module_name: str) -> List[StubCandidate]:
    out: List[StubCandidate] = []
    for stmt in getattr(tree, "body", []):
        if not isinstance(stmt, ast.Try):
            continue
        for h in stmt.handlers:
            is_exc = False
            if h.type is None:
                is_exc = True
            elif isinstance(h.type, ast.Name) and h.type.id in {"Exception", "BaseException"}:
                is_exc = True
            elif isinstance(h.type, ast.Tuple):
                names = [x.id for x in h.type.elts if isinstance(x, ast.Name)]
                is_exc = any(n in {"Exception", "BaseException"} for n in names)
            if not is_exc:
                continue
            if h.body and all(isinstance(x, ast.Pass) for x in h.body):
                st = int(getattr(h, "lineno", getattr(stmt, "lineno", 1)))
                en = int(getattr(h, "end_lineno", st))
                out.append(
                    StubCandidate(
                        path=rel_path,
                        module=module_name,
                        symbol="__module__",
                        stub_kind="suppress_init",
                        line_start=st,
                        line_end=en,
                        excerpt=_path_excerpt(lines, st, en),
                    )
                )
    return out


def _detect_function_stub(
    fn: ast.AST,
    symbol: str,
    lines: List[str],
    rel_path: str,
    module_name: str,
    exports: Set[str],
) -> Optional[StubCandidate]:
    body = list(getattr(fn, "body", []) or [])
    body_wo_doc = _strip_docstring_body(body)
    st = int(getattr(fn, "lineno", 1))
    en = int(getattr(fn, "end_lineno", st))
    line_count = max(1, en - st + 1)
    fn_text = "\n".join(lines[max(0, st - 1) : min(len(lines), en)])
    has_todo_marker = bool(TODO_RE.search(fn_text))
    name_leaf = symbol.split(".")[-1] if symbol else ""
    exported = name_leaf in exports

    stub_kind = ""
    marker = ""
    if not body_wo_doc:
        stub_kind = "pass_only"
    elif all(isinstance(x, ast.Pass) for x in body_wo_doc):
        stub_kind = "pass_only"
    elif len(body_wo_doc) == 1 and _is_ellipsis_stmt(body_wo_doc[0]):
        stub_kind = "ellipsis"
    elif any(_is_raise_not_implemented(x) for x in body_wo_doc):
        stub_kind = "not_implemented"
    elif line_count < 15 and _has_ok_dict_return(fn) and has_todo_marker:
        stub_kind = "placeholder_return"
        marker = "ok_true_short"
    elif line_count < 15 and _has_return_none(fn) and (exported or has_todo_marker):
        stub_kind = "placeholder_return"
        marker = "return_none_short"
    elif has_todo_marker:
        stub_kind = "todo_marker"

    if not stub_kind:
        return None
    return StubCandidate(
        path=rel_path,
        module=module_name,
        symbol=symbol,
        stub_kind=stub_kind,
        line_start=st,
        line_end=en,
        excerpt=_path_excerpt(lines, st, en),
        marker=marker,
    )


def _scan_module(path: Path, rel_path: str, module_name: str, enable_stubs: bool) -> ModuleInfo:
    text = _read_text(path)
    lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return ModuleInfo(path=path, rel_path=rel_path, module=module_name, imports=set(), names=set(), stub_candidates=[])

    imports, names, exports = _module_imports_and_names(tree, module_name)
    stubs: List[StubCandidate] = []

    if enable_stubs:
        stubs.extend(_module_level_suppress_init(tree, lines, rel_path, module_name))
        parents = _set_parent_map(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = _function_symbol(node, parents)
                cand = _detect_function_stub(node, symbol, lines, rel_path, module_name, exports)
                if cand is not None:
                    stubs.append(cand)
            elif isinstance(node, ast.ClassDef):
                body_wo_doc = _strip_docstring_body(node.body)
                if body_wo_doc and all(isinstance(x, ast.Pass) for x in body_wo_doc):
                    st = int(getattr(node, "lineno", 1))
                    en = int(getattr(node, "end_lineno", st))
                    stubs.append(
                        StubCandidate(
                            path=rel_path,
                            module=module_name,
                            symbol=node.name,
                            stub_kind="pass_only",
                            line_start=st,
                            line_end=en,
                            excerpt=_path_excerpt(lines, st, en),
                        )
                    )

    return ModuleInfo(
        path=path,
        rel_path=rel_path,
        module=module_name,
        imports=imports,
        names=names,
        stub_candidates=stubs,
    )


def _stronger_reason(cur: str, new: str) -> str:
    if REASON_PRIORITY.get(new, 0) > REASON_PRIORITY.get(cur, 0):
        return new
    return cur

def _parse_route_modules(route_registry_path: Path) -> List[str]:
    if not route_registry_path.exists():
        return []
    text = _read_text(route_registry_path)
    try:
        tree = ast.parse(text, filename=str(route_registry_path))
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ROUTE_MODULES":
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception:
                        return []
                    out: List[str] = []
                    if isinstance(value, (list, tuple)):
                        for x in value:
                            if isinstance(x, str) and x.strip():
                                out.append(x.strip())
                    return out
    return []


def _collect_register_calls(path: Path, module_name: str) -> Dict[str, Set[str]]:
    text = _read_text(path)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return {}
    out: Dict[str, Set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        fn_name = ""
        if isinstance(node.func, ast.Name):
            fn_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            fn_name = node.func.attr
        if fn_name != "register":
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            aid = first.value.strip()
            if aid:
                out.setdefault(aid, set()).add(module_name)
    return out


def _parse_template_actions(pack_path: Path) -> Dict[str, List[str]]:
    if not pack_path.exists():
        return {}
    text = _read_text(pack_path)
    try:
        tree = ast.parse(text, filename=str(pack_path))
    except SyntaxError:
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PACK_V1":
                    try:
                        val = ast.literal_eval(node.value)
                    except Exception:
                        return {}
                    out: Dict[str, List[str]] = {}
                    if isinstance(val, list):
                        for item in val:
                            if not isinstance(item, dict):
                                continue
                            tid = str(item.get("id") or "").strip()
                            acts = item.get("default_allowed_actions")
                            if not tid or not isinstance(acts, list):
                                continue
                            arr = [str(x).strip() for x in acts if str(x).strip()]
                            out[tid] = arr
                    return out
    return {}


def _parse_aliases(alias_path: Path) -> Dict[str, List[str]]:
    if not alias_path.exists():
        return {}
    text = _read_text(alias_path)
    try:
        tree = ast.parse(text, filename=str(alias_path))
    except SyntaxError:
        return {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STABLE_ACTION_ALIASES":
                    try:
                        val = ast.literal_eval(node.value)
                    except Exception:
                        return {}
                    out: Dict[str, List[str]] = {}
                    if isinstance(val, dict):
                        for k, v in val.items():
                            kk = str(k).strip()
                            if not kk or not isinstance(v, list):
                                continue
                            out[kk] = [str(x).strip() for x in v if str(x).strip()]
                    return out
    return {}


def _module_path_from_name(repo_root: Path, module_name: str) -> Optional[Path]:
    rel = Path(module_name.replace(".", "/"))
    py = (repo_root / rel).with_suffix(".py")
    if py.exists():
        return py
    init = repo_root / rel / "__init__.py"
    if init.exists():
        return init
    return None


def _stable_id(path: str, symbol: str, kind: str) -> str:
    raw = f"{path}|{symbol}|{kind}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _suggest_fix(kind: str) -> str:
    if kind in {"pass_only", "ellipsis"}:
        return "Replace empty body with real implementation and add minimal smoke coverage."
    if kind == "not_implemented":
        return "Implement the contract and keep explicit failure paths only for impossible branches."
    if kind == "placeholder_return":
        return "Replace placeholder return with real logic/validation and meaningful output."
    if kind == "todo_marker":
        return "Resolve TODO/FIXME/STUB marker or convert to tracked issue outside runtime path."
    if kind == "suppress_init":
        return "Replace silent suppression with explicit logging + deterministic fallback."
    return "Implement concrete behavior."


def _suggest_owner(path: str) -> str:
    p = path.replace("\\", "/").lower()
    if "/memory/" in p:
        return "archivist"
    if "/routes/" in p:
        return "reviewer"
    if "/garage/" in p or "/proactivity/" in p:
        return "builder"
    if "/security/" in p:
        return "reviewer"
    return "reviewer"


def _score_stub(kind: str, reachable: bool, reason: str, ref_count: int) -> int:
    score = int(STUB_BASE_SCORE.get(kind, 50))
    if reachable:
        score += 20
    if reason in {"entry", "route", "action", "template"}:
        score += 10
    score += min(20, max(0, int(ref_count)) * 2)
    if kind == "todo_marker" and not reachable:
        score -= 10
    return max(0, min(100, score))


def _collect_app_py_entrypoints(repo_root: Path) -> int:
    # Count direct launch patterns in Python files only.
    py_files: List[Path] = []
    for base in ("tests", "tools"):
        root = repo_root / base
        if root.exists():
            py_files.extend(_iter_py_files(root))
    launch_re = re.compile(r"\bpython(?:\.exe)?\b[^\n\r#]*\bapp\.py\b", re.IGNORECASE)
    n = 0
    for p in py_files:
        text = _read_text(p)
        if launch_re.search(text):
            n += 1
    return n


def _build_markdown(
    *,
    top_rows: List[Dict[str, Any]],
    all_rows: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> str:
    kind_counts = dict(summary.get("stub_kinds") or {})
    total = int(summary.get("total_stubs") or 0)
    reachable = int(summary.get("reachable_stubs") or 0)
    app_py_entrypoints = int(summary.get("app_py_entrypoints") or 0)

    lines: List[str] = []
    lines.append("# Stubs Kill List")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- total_stubs: {total}")
    lines.append(f"- reachable_stubs: {reachable}")
    lines.append(f"- app_py_entrypoints: {app_py_entrypoints}")
    lines.append(f"- top_stub_kinds: {json.dumps(kind_counts, ensure_ascii=False)}")
    lines.append("")
    lines.append("## Top-30")
    lines.append("")
    lines.append("| rank | severity | reachable | path:symbol | stub_kind | reach_reason | refs | suggested_fix |")
    lines.append("|---:|---:|:---:|---|---|---|---:|---|")
    for i, row in enumerate(top_rows[:30], start=1):
        path_symbol = f"{row['path']}:{row['symbol']}"
        lines.append(
            f"| {i} | {row['severity_score']} | {str(bool(row['reachable'])).lower()} | "
            f"{path_symbol} | {row['stub_kind']} | {row['reach_reason']} | {row['ref_count']} | "
            f"{row['suggested_fix']} |"
        )
    lines.append("")

    p0 = [r for r in all_rows if r["bucket"] == "P0"]
    p1 = [r for r in all_rows if r["bucket"] == "P1"]
    p2 = [r for r in all_rows if r["bucket"] == "P2"]

    lines.append("## Kill Order")
    lines.append("")
    lines.append(f"- P0 (runtime critical): {len(p0)}")
    for row in p0[:15]:
        lines.append(f"  - {row['path']}:{row['symbol']} [{row['stub_kind']}]")
    lines.append(f"- P1 (planned features): {len(p1)}")
    for row in p1[:15]:
        lines.append(f"  - {row['path']}:{row['symbol']} [{row['stub_kind']}]")
    lines.append(f"- P2 (cleanup): {len(p2)}")
    for row in p2[:15]:
        lines.append(f"  - {row['path']}:{row['symbol']} [{row['stub_kind']}]")
    lines.append("")

    chosen = p0[:10] if p0 else p1[:10]
    if len(chosen) < 5:
        chosen = (p0 + p1)[:10]
    touch = sorted({str(r["path"]) for r in chosen})
    lines.append("## Next Iteration Plan (Iter34)")
    lines.append("")
    lines.append("- Proposed focus: fix highest reachable P0/P1 stubs first.")
    lines.append("- Suggested touch list:")
    for p in touch:
        lines.append(f"  - {p}")
    lines.append("- Acceptance checks:")
    lines.append("  - powershell -File tools/run_checks_offline.ps1 -NoGitGuard -Quiet")
    lines.append("  - python -B tools/stubs_kill_list.py --root modules --entry run_ester_fixed.py --out-md docs/stubs_kill_list.md --out-jsonl data/reports/stubs_kill_list.jsonl --top 100")
    lines.append("  - python -B tools/stubs_kill_list.py --smoke 1")
    lines.append("")
    lines.append("## Bridges")
    lines.append("")
    lines.append("- Explicit bridge (Ashby): the regulator must know the real system; The priority of edits is set by reachability from the rintite.")
    lines.append("- Hidden bridge #1 (Enderton): eksport simvola bez smysla (pass) lomaet dokazuemost kontrakta vyzova.")
    lines.append("- Hidden bridge #2 (Carpet&Thomas): ranking by rehabilitation/ref_count reduces the entropy of edits and enhances the useful signal.")
    lines.append("")
    lines.append("## Earth Paragraph")
    lines.append("")
    lines.append("It’s like flaw detection of welds: first we look for cracks on loaded units (rehabilier),")
    lines.append("and not on decorative panels. Otherwise, you can polish the “cosmetics” for a long time, and a rupture will happen there,")
    lines.append("where pressure and vibration are real (proactivities/agents/rutes).")
    lines.append("")
    return "\n".join(lines)

def run_scan(
    *,
    repo_root: Path,
    root_name: str,
    include_routes: bool,
    entry_file: str,
    out_md: Path,
    out_jsonl: Path,
    top_n: int,
) -> Dict[str, Any]:
    scan_files: List[Tuple[Path, str, bool]] = []

    modules_root = (repo_root / root_name).resolve()
    if not modules_root.exists():
        raise RuntimeError(f"scan root not found: {modules_root}")
    for p in _iter_py_files(modules_root):
        mod = _module_from_file(p, modules_root, root_name)
        scan_files.append((p, mod, True))

    if include_routes:
        routes_root = (repo_root / "routes").resolve()
        if routes_root.exists():
            for p in _iter_py_files(routes_root):
                mod = _module_from_file(p, routes_root, "routes")
                scan_files.append((p, mod, True))

    entry_path = (repo_root / entry_file).resolve()
    if entry_path.exists():
        scan_files.append((entry_path, "run_ester_fixed", False))

    route_registry = (repo_root / "routes" / "route_registry.py").resolve()
    route_modules = _parse_route_modules(route_registry)
    if route_registry.exists():
        scan_files.append((route_registry, "routes.route_registry", False))
    for rm in route_modules:
        rp = _module_path_from_name(repo_root, rm)
        if rp is not None:
            scan_files.append((rp, rm, False))

    uniq: Dict[str, Tuple[Path, str, bool]] = {}
    for p, mod, stub_enabled in scan_files:
        key = _as_posix(p.resolve())
        cur = uniq.get(key)
        if cur is None:
            uniq[key] = (p, mod, stub_enabled)
        else:
            uniq[key] = (p, mod, bool(cur[2] or stub_enabled))

    modules: Dict[str, ModuleInfo] = {}
    scanned_modules: Set[str] = set()
    action_id_to_modules: Dict[str, Set[str]] = {}

    for _, (path, mod, stubs_enabled) in sorted(uniq.items(), key=lambda x: x[0]):
        rel = _as_posix(path.relative_to(repo_root))
        info = _scan_module(path, rel, mod, stubs_enabled)
        modules[mod] = info
        if stubs_enabled:
            scanned_modules.add(mod)
        if mod.startswith("modules.thinking.actions") or mod == "modules.thinking.action_registry":
            reg_calls = _collect_register_calls(path, mod)
            for aid, owners in reg_calls.items():
                action_id_to_modules.setdefault(aid, set()).update(owners)

    graph: Dict[str, Set[str]] = {m: set() for m in sorted(scanned_modules)}
    for mod in sorted(scanned_modules):
        info = modules.get(mod)
        if info is None:
            continue
        for imp in sorted(info.imports):
            if imp in scanned_modules:
                graph[mod].add(imp)

    importers: Dict[str, Set[str]] = {m: set() for m in sorted(scanned_modules)}
    for src, deps in graph.items():
        for dep in deps:
            importers.setdefault(dep, set()).add(src)

    seed_reason: Dict[str, str] = {}

    def add_seed(module_name: str, reason: str) -> None:
        if module_name not in scanned_modules:
            return
        prev = seed_reason.get(module_name, "unknown")
        seed_reason[module_name] = _stronger_reason(prev, reason)

    if entry_path.exists():
        entry_info = _scan_module(entry_path, _as_posix(entry_path.relative_to(repo_root)), "run_ester_fixed", False)
        for imp in sorted(entry_info.imports):
            add_seed(imp, "entry")

    for rm in route_modules:
        add_seed(rm, "route")
        rpath = _module_path_from_name(repo_root, rm)
        if rpath is None:
            continue
        rinfo = _scan_module(rpath, _as_posix(rpath.relative_to(repo_root)), rm, False)
        for imp in sorted(rinfo.imports):
            add_seed(imp, "route")

    pack_path = (repo_root / "modules" / "garage" / "templates" / "pack_v1.py").resolve()
    registry_path = (repo_root / "modules" / "garage" / "templates" / "registry.py").resolve()
    template_actions = _parse_template_actions(pack_path)
    action_aliases = _parse_aliases(registry_path)
    for _, acts in sorted(template_actions.items(), key=lambda kv: kv[0]):
        for act in acts:
            aliases = [act] + list(action_aliases.get(act, []))
            for alias in aliases:
                owners = action_id_to_modules.get(alias, set())
                for owner in sorted(owners):
                    add_seed(owner, "template")

    add_seed("modules.thinking.action_registry", "action")

    reachable_reason: Dict[str, str] = {}
    stack: List[str] = []
    for m, r in sorted(seed_reason.items()):
        reachable_reason[m] = r
        stack.append(m)

    while stack:
        cur = stack.pop()
        for nxt in sorted(graph.get(cur, set())):
            if nxt not in reachable_reason:
                reachable_reason[nxt] = "import_only"
                stack.append(nxt)
            else:
                prev = reachable_reason[nxt]
                upgraded = _stronger_reason(prev, "import_only")
                if upgraded != prev:
                    reachable_reason[nxt] = upgraded

    reachable_modules = set(reachable_reason.keys())
    symbol_refs: Dict[str, Set[str]] = {}
    for mod, info in modules.items():
        if mod not in scanned_modules:
            continue
        for nm in info.names:
            symbol_refs.setdefault(nm, set()).add(mod)

    rows: List[Dict[str, Any]] = []
    for mod in sorted(scanned_modules):
        info = modules.get(mod)
        if info is None:
            continue
        mod_importers = importers.get(mod, set())
        for cand in info.stub_candidates:
            symbol_leaf = cand.symbol.split(".")[-1]
            name_refs = symbol_refs.get(symbol_leaf, set())
            refs = set(mod_importers) | {m for m in name_refs if m != mod}
            ref_count = len(refs)
            mod_reach_reason = reachable_reason.get(mod, "unknown")
            reachable = mod in reachable_modules
            reach_reason = mod_reach_reason
            if not reachable and name_refs & reachable_modules:
                reachable = True
                reach_reason = "import_only"

            severity = _score_stub(cand.stub_kind, reachable, reach_reason, ref_count)
            row = {
                "id": _stable_id(cand.path, cand.symbol, cand.stub_kind),
                "path": cand.path,
                "module": cand.module,
                "symbol": cand.symbol,
                "stub_kind": cand.stub_kind,
                "excerpt": cand.excerpt,
                "line_start": int(cand.line_start),
                "line_end": int(cand.line_end),
                "severity_score": int(severity),
                "reachable": bool(reachable),
                "reach_reason": reach_reason,
                "ref_count": int(ref_count),
                "suggested_fix": _suggest_fix(cand.stub_kind),
                "suggested_owner_agent": _suggest_owner(cand.path),
            }
            rows.append(row)

    rows.sort(
        key=lambda r: (
            -int(r["severity_score"]),
            -int(1 if r["reachable"] else 0),
            -int(r["ref_count"]),
            str(r["path"]),
            str(r["symbol"]),
            str(r["stub_kind"]),
        )
    )

    for row in rows:
        reachable = bool(row["reachable"])
        reason = str(row["reach_reason"])
        sev = int(row["severity_score"])
        path_low = str(row["path"]).lower()
        if reachable and reason in {"entry", "route", "action", "template"} and sev >= 80:
            bucket = "P0"
        elif reachable and (("proactivity/" in path_low) or ("garage/" in path_low) or ("memory/" in path_low) or sev >= 60):
            bucket = "P1"
        else:
            bucket = "P2"
        row["bucket"] = bucket

    kind_counts: Dict[str, int] = {}
    for row in rows:
        k = str(row["stub_kind"])
        kind_counts[k] = int(kind_counts.get(k, 0)) + 1
    kind_counts = dict(sorted(kind_counts.items(), key=lambda kv: (-kv[1], kv[0])))

    app_py_entrypoints = _collect_app_py_entrypoints(repo_root)
    summary = {
        "ok": True,
        "total_stubs": len(rows),
        "reachable_stubs": sum(1 for r in rows if bool(r["reachable"])),
        "top_stub_kinds": list(kind_counts.items())[:10],
        "stub_kinds": kind_counts,
        "top10": rows[:10],
        "app_py_entrypoints": int(app_py_entrypoints),
    }

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    md = _build_markdown(top_rows=rows[: max(1, int(top_n))], all_rows=rows, summary=summary)
    out_md.write_text(md, encoding="utf-8")

    return summary


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Find and rank stubs by runtime reachability (offline, stdlib-only).")
    ap.add_argument("--root", default="modules")
    ap.add_argument("--include-routes", default="0")
    ap.add_argument("--entry", default="run_ester_fixed.py")
    ap.add_argument("--out-md", default="docs/stubs_kill_list.md")
    ap.add_argument("--out-jsonl", default="data/reports/stubs_kill_list.jsonl")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--smoke", default="0")
    args = ap.parse_args(argv)

    repo_root = Path.cwd().resolve()
    include_routes = str(args.include_routes).strip() in {"1", "true", "yes", "on", "y"}
    smoke = str(args.smoke).strip() in {"1", "true", "yes", "on", "y"}

    out_md = (repo_root / str(args.out_md)).resolve()
    out_jsonl = (repo_root / str(args.out_jsonl)).resolve()

    try:
        summary = run_scan(
            repo_root=repo_root,
            root_name=str(args.root).strip() or "modules",
            include_routes=bool(include_routes),
            entry_file=str(args.entry).strip() or "run_ester_fixed.py",
            out_md=out_md,
            out_jsonl=out_jsonl,
            top_n=max(1, int(args.top or 100)),
        )
        if smoke:
            ok = (
                out_md.exists()
                and out_jsonl.exists()
                and int(summary.get("total_stubs") or 0) >= 0
                and int(summary.get("reachable_stubs") or 0) >= 0
                and int(summary.get("app_py_entrypoints") or 0) == 0
            )
            summary["smoke"] = {"ok": bool(ok), "out_md": str(out_md), "out_jsonl": str(out_jsonl)}
            print(json.dumps(summary, ensure_ascii=True, indent=2))
            return 0 if ok else 2

        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return 0
    except Exception as exc:
        out = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
