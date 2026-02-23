# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("modules", "routes", "tools", "bin")
OUT_MD = ROOT / "deps_report.md"


DYNAMIC_PATTERNS: Sequence[Tuple[str, str, int]] = (
    ("importlib.import_module", r"\bimportlib\.import_module\s*\(", 10),
    ("pkgutil.iter_modules", r"\bpkgutil\.iter_modules\s*\(", 9),
    ("__import__", r"\b__import__\s*\(", 9),
    ("eval", r"\beval\s*\(", 8),
    ("exec", r"\bexec\s*\(", 8),
    ("glob.glob", r"\bglob\.glob\s*\(", 5),
)


AUTODISCOVERY_MARKERS: Sequence[Tuple[str, int]] = (
    ("route_modules", 8),
    ("ESTER_EXTRA_ROUTE_MODULES", 8),
    ("register_blueprint", 4),
    ("discover", 5),
    ("plugin", 5),
    ("loader", 5),
)


@dataclass
class FileScan:
    rel: str
    module_name: str
    imports: List[str]
    syntax_error: str
    dynamic_hits: List[str]
    autodiscovery_score: int
    source: str


def _iter_py_files() -> Iterable[Path]:
    for name in SCAN_DIRS:
        base = ROOT / name
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            parts = {x.lower() for x in p.parts}
            if "__pycache__" in parts:
                continue
            yield p


def _module_name(rel: str) -> str:
    rel_no_ext = rel[:-3] if rel.endswith(".py") else rel
    rel_no_ext = rel_no_ext.replace("\\", "/")
    if rel_no_ext.endswith("/__init__"):
        rel_no_ext = rel_no_ext[: -len("/__init__")]
    return rel_no_ext.replace("/", ".")


def _parse_imports(text: str) -> Tuple[List[str], str]:
    imports: List[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return imports, f"{type(exc).__name__}: {exc.msg} (line {exc.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = str(alias.name or "").strip()
                if name:
                    imports.append(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(str(node.module))
    return imports, ""


def _scan_file(path: Path) -> FileScan:
    rel = str(path.relative_to(ROOT)).replace("/", "\\")
    module_name = _module_name(rel)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    imports, syntax_error = _parse_imports(text)

    dynamic_hits: List[str] = []
    for label, pattern, _score in DYNAMIC_PATTERNS:
        if re.search(pattern, text):
            dynamic_hits.append(label)

    score = 0
    lowered = text.lower()
    for marker, points in AUTODISCOVERY_MARKERS:
        if marker.lower() in lowered:
            score += points
    if dynamic_hits:
        score += sum(points for label, _p, points in DYNAMIC_PATTERNS if label in dynamic_hits)

    return FileScan(
        rel=rel,
        module_name=module_name,
        imports=imports,
        syntax_error=syntax_error,
        dynamic_hits=dynamic_hits,
        autodiscovery_score=score,
        source=text,
    )


def _normalize_candidate(stem: str) -> str:
    out = re.sub(r"[_\-\s]+", "", stem.casefold())
    return out


def _duplicates(files: Sequence[FileScan]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)
    for f in files:
        stem = Path(f.rel).stem
        cand = _normalize_candidate(stem)
        groups[cand].append(f.rel)
    dup = {
        k: sorted(v)
        for k, v in groups.items()
        if len(v) > 1
    }
    return dict(sorted(dup.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def _top_packages(files: Sequence[FileScan], n: int = 12) -> List[Tuple[str, int]]:
    cnt: Counter[str] = Counter()
    for f in files:
        for imp in f.imports:
            head = imp.split(".", 1)[0].strip()
            if head:
                cnt[head] += 1
    return cnt.most_common(n)


def _collect_risk_points(files: Sequence[FileScan], dups: Dict[str, List[str]], limit: int = 10) -> List[str]:
    points: List[Tuple[int, str]] = []

    for f in files:
        if f.dynamic_hits:
            weight = 20 + (3 * len(f.dynamic_hits))
            points.append((weight, f"{f.rel}: dynamic imports/hooks -> {', '.join(sorted(set(f.dynamic_hits)))}"))
        if f.autodiscovery_score >= 10:
            points.append((f.autodiscovery_score, f"{f.rel}: autodiscovery seams score={f.autodiscovery_score}"))
        if f.syntax_error:
            points.append((7, f"{f.rel}: syntax parse issue -> {f.syntax_error}"))

    for cand, paths in dups.items():
        weight = min(25, 5 + len(paths))
        points.append((weight, f"duplicate-name candidate '{cand}': {len(paths)} paths"))

    points.sort(key=lambda x: (-x[0], x[1]))
    out: List[str] = []
    seen: Set[str] = set()
    for _w, text in points:
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _build_adjacency(files: Sequence[FileScan]) -> Dict[str, Set[str]]:
    module_set = {f.module_name for f in files}
    adj: Dict[str, Set[str]] = {f.module_name: set() for f in files}
    for f in files:
        for imp in f.imports:
            if imp in module_set:
                adj[f.module_name].add(imp)
                continue
            prefix = imp
            while "." in prefix:
                prefix = prefix.rsplit(".", 1)[0]
                if prefix in module_set:
                    adj[f.module_name].add(prefix)
                    break
    return adj


def _bfs_path(adj: Dict[str, Set[str]], starts: Sequence[str], is_target) -> List[str]:
    q: deque[str] = deque()
    prev: Dict[str, str] = {}
    seen: Set[str] = set()
    for s in starts:
        if s in adj:
            q.append(s)
            seen.add(s)
    while q:
        cur = q.popleft()
        if is_target(cur):
            path = [cur]
            while cur in prev:
                cur = prev[cur]
                path.append(cur)
            path.reverse()
            return path
        for nxt in sorted(adj.get(cur, set())):
            if nxt in seen:
                continue
            seen.add(nxt)
            prev[nxt] = cur
            q.append(nxt)
    return []


def _telegram_trace(files: Sequence[FileScan]) -> str:
    adj = _build_adjacency(files)
    modules = {f.module_name for f in files}
    starts = [m for m in modules if "telegram" in m and m.startswith("routes.")]
    if not starts:
        starts = [m for m in modules if "telegram" in m]

    memory_path = _bfs_path(adj, starts, lambda m: m.startswith("modules.memory"))
    vector_path = _bfs_path(adj, memory_path[-1:] if memory_path else starts, lambda m: "vector" in m)

    chain: List[str] = []
    if memory_path:
        chain.extend(memory_path)
    if vector_path:
        if chain and chain[-1] == vector_path[0]:
            chain.extend(vector_path[1:])
        else:
            chain.extend(vector_path)

    if not chain and starts:
        chain = [starts[0]]

    if not chain:
        return "best-effort trace unavailable: no telegram-related modules found in scanned graph."

    return " -> ".join(chain) + " -> flask.response/jsonify (runtime response edge)"


def _render_markdown(files: Sequence[FileScan], dups: Dict[str, List[str]]) -> str:
    edges = sum(len(f.imports) for f in files)
    top_pkgs = _top_packages(files, n=12)
    risks = _collect_risk_points(files, dups, limit=10)
    trace = _telegram_trace(files)

    lines: List[str] = []
    lines.append("# deps_report")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- files_scanned: {len(files)}")
    lines.append(f"- import_edges: {edges}")
    lines.append(f"- syntax_parse_failures: {sum(1 for f in files if f.syntax_error)}")
    lines.append("")
    lines.append("### Top Packages")
    for pkg, cnt in top_pkgs:
        lines.append(f"- {pkg}: {cnt}")
    lines.append("")
    lines.append("## Top-10 Risk Points")
    if risks:
        for i, item in enumerate(risks, start=1):
            lines.append(f"{i}. {item}")
    else:
        lines.append("1. No risk points detected by current heuristics.")
    lines.append("")
    lines.append("## Mini Trace: telegram -> routing -> memory -> vector store -> response")
    lines.append(f"- {trace}")
    lines.append("")
    lines.append("## Duplicate Candidates")
    lines.append("| candidate_name | paths[] | why_risky |")
    lines.append("|---|---|---|")
    if dups:
        for cand, paths in dups.items():
            joined = "<br>".join(paths)
            lines.append(
                f"| `{cand}` | {joined} | Windows/casefold import ambiguity + loader drift risk |"
            )
    else:
        lines.append("| `none` | - | No duplicate candidates found |")
    lines.append("")
    lines.append("## Notes")
    lines.append("- Explicit bridge (Ashby): observability before control; this report is the minimum dependency observability layer.")
    lines.append("- Hidden bridge #1 (Cover-Thomas): import/autoload fanout lowers causal clarity under bounded channel capacity.")
    lines.append("- Hidden bridge #2 (Guyton-Hall): restored endpoint return-paths re-close the stimulus-response loop.")
    lines.append("")
    lines.append("## Earth Paragraph")
    lines.append(
        "Hydraulic analogy: missing `return` is a missing check valve; pump runs, pressure does not return to the circuit, so you get 500-cavitation. "
        "Closed-box outbound is a leak in a sealed chamber; even rare leaks are still leaks. Fix valves first (returns), then plug the chamber (network deny), then map pipes (deps report)."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    files = [_scan_file(p) for p in sorted(_iter_py_files())]
    dups = _duplicates(files)
    report = _render_markdown(files, dups)
    OUT_MD.write_text(report, encoding="utf-8")
    print(f"deps_report_written={OUT_MD}")
    print(f"files_scanned={len(files)}")
    print(f"import_edges={sum(len(f.imports) for f in files)}")
    print(f"duplicate_candidates={len(dups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
