# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

HTTP_DECORATORS: Dict[str, str] = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "head": "HEAD",
    "options": "OPTIONS",
}
URL_FOR_RE = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
SMOKE_SECTION_BEGIN = "<!-- UI_HTTP_SMOKE:BEGIN -->"
SMOKE_SECTION_END = "<!-- UI_HTTP_SMOKE:END -->"
TMP_UI_SERVER_REL = Path("tools/_tmp_ui_server.py")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _const_str(node: Optional[ast.AST]) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _extract_methods(call: ast.Call, decorator: str) -> List[str]:
    if decorator in HTTP_DECORATORS:
        return [HTTP_DECORATORS[decorator]]

    methods: List[str] = []
    for kw in call.keywords:
        if kw.arg != "methods":
            continue
        value = kw.value
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            for item in value.elts:
                s = _const_str(item)
                if s:
                    methods.append(s.upper())
        else:
            single = _const_str(value)
            if single:
                methods.append(single.upper())
    if not methods:
        methods = ["GET"]
    return sorted(set(methods))


def _join_rule(prefix: str, rule: str) -> str:
    p = (prefix or "").strip()
    r = (rule or "").strip()
    if not r:
        r = "/"
    if not r.startswith("/"):
        r = "/" + r
    if not p:
        return r
    if not p.startswith("/"):
        p = "/" + p
    if p.endswith("/") and r.startswith("/"):
        return p[:-1] + r
    return p + r


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _template_files(templates_dir: Path) -> List[str]:
    if not templates_dir.is_dir():
        return []
    out: List[str] = []
    for p in templates_dir.rglob("*.html"):
        out.append(p.relative_to(templates_dir).as_posix())
    out.sort()
    return out


def _portal_guess(templates_dir: Path, templates: Sequence[str]) -> str:
    best_name = ""
    best_score = -1
    for rel in templates:
        rel_low = rel.lower()
        base_low = Path(rel).name.lower()
        score = 0
        if rel_low == "portal.html":
            score += 1000
        if base_low.startswith("portal"):
            score += 200
        elif "portal" in base_low:
            score += 80
        if "/portal" in ("/" + rel_low):
            score += 30

        path = templates_dir / rel
        snippet = _read_text(path)[:4096].lower()
        if "<title" in snippet and "portal" in snippet:
            score += 20
        if "<h1" in snippet and "portal" in snippet:
            score += 15
        if "<nav" in snippet and "portal" in snippet:
            score += 10

        if score > best_score:
            best_score = score
            best_name = rel
    return best_name


def _module_uses_fastapi(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.name or "").strip()
                if name == "fastapi" or name.startswith("fastapi."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").strip()
            if module == "fastapi" or module.startswith("fastapi."):
                return True
    return False


def _extract_blueprints(tree: ast.Module) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for stmt in tree.body:
        value: Optional[ast.AST] = None
        targets: List[ast.AST] = []
        if isinstance(stmt, ast.Assign):
            value = stmt.value
            targets = list(stmt.targets)
        elif isinstance(stmt, ast.AnnAssign):
            value = stmt.value
            targets = [stmt.target]
        if not isinstance(value, ast.Call):
            continue
        if _call_name(value.func) != "Blueprint":
            continue

        bp_name = _const_str(value.args[0]) if value.args else None
        if not bp_name:
            bp_name = ""
        url_prefix = ""
        for kw in value.keywords:
            if kw.arg == "url_prefix":
                prefix_val = _const_str(kw.value)
                if prefix_val:
                    url_prefix = prefix_val
        for target in targets:
            if isinstance(target, ast.Name):
                out[target.id] = {"name": bp_name or target.id, "url_prefix": url_prefix}
    return out


def _render_templates_in_fn(fn: ast.AST) -> List[Tuple[str, int]]:
    found: Set[Tuple[str, int]] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name != "render_template":
            continue
        template = _const_str(node.args[0]) if node.args else None
        if template:
            found.add((template, getattr(node, "lineno", 0)))
    return sorted(found, key=lambda item: (item[0], item[1]))


def _decorator_route_info(
    dec: ast.AST, blueprints: Dict[str, Dict[str, str]], fn_name: str
) -> Optional[Dict[str, Any]]:
    if not isinstance(dec, ast.Call):
        return None
    if not isinstance(dec.func, ast.Attribute):
        return None

    decorator = (dec.func.attr or "").lower()
    if decorator not in set(HTTP_DECORATORS).union({"route"}):
        return None

    bp_ref = dec.func.value
    if not isinstance(bp_ref, ast.Name):
        return None
    bp = blueprints.get(bp_ref.id)
    if not bp:
        return None

    rule = _const_str(dec.args[0]) if dec.args else None
    if not rule:
        for kw in dec.keywords:
            if kw.arg == "rule":
                rule = _const_str(kw.value)
    if not rule:
        return None

    endpoint_local = fn_name
    for kw in dec.keywords:
        if kw.arg == "endpoint":
            endpoint_val = _const_str(kw.value)
            if endpoint_val:
                endpoint_local = endpoint_val
    endpoint = (
        endpoint_local
        if "." in endpoint_local
        else f"{bp['name']}.{endpoint_local}"
    )

    return {
        "rule": _join_rule(bp.get("url_prefix", ""), rule),
        "methods": _extract_methods(dec, decorator),
        "endpoint": endpoint,
        "blueprint": bp.get("name", bp_ref.id),
    }


def _iter_function_nodes(tree: ast.Module) -> Iterable[ast.AST]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def analyze_project(project_root: Path) -> Dict[str, Any]:
    templates_dir = project_root / "templates"
    routes_dir = project_root / "routes"

    templates_files = _template_files(templates_dir)
    templates_set = set(templates_files)
    portal_guess = _portal_guess(templates_dir, templates_files)

    flask_render_routes: List[Dict[str, Any]] = []
    referenced_templates: Set[str] = set()
    missing_templates_set: Set[str] = set()
    fastapi_template_violations: List[Dict[str, Any]] = []
    parse_errors: List[Dict[str, str]] = []
    all_route_entries: List[Dict[str, Any]] = []

    if routes_dir.is_dir():
        route_files = sorted(routes_dir.rglob("*.py"))
    else:
        route_files = []

    for path in route_files:
        rel_file = path.relative_to(project_root).as_posix()
        text = _read_text(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            parse_errors.append(
                {
                    "file": rel_file,
                    "error": f"SyntaxError:{exc.lineno}:{exc.offset}: {exc.msg}",
                }
            )
            continue

        uses_fastapi = _module_uses_fastapi(tree)
        blueprints = _extract_blueprints(tree)

        for fn in _iter_function_nodes(tree):
            fn_name = getattr(fn, "name", "<unknown>")
            template_hits = _render_templates_in_fn(fn)
            template_names = sorted({tpl for tpl, _ in template_hits})
            referenced_templates.update(template_names)

            for template_name in template_names:
                if template_name not in templates_set:
                    missing_templates_set.add(template_name)

            if uses_fastapi and template_hits:
                for template_name, lineno in template_hits:
                    fastapi_template_violations.append(
                        {
                            "file": rel_file,
                            "line": lineno,
                            "template": template_name,
                            "reason": "render_template in module importing fastapi",
                        }
                    )

            route_entries: List[Dict[str, Any]] = []
            for dec in getattr(fn, "decorator_list", []):
                route_info = _decorator_route_info(dec, blueprints, fn_name)
                if route_info:
                    all_route_entries.append(
                        {
                            "file": rel_file,
                            "rule": route_info["rule"],
                            "methods": list(route_info["methods"]),
                            "endpoint": route_info["endpoint"],
                            "blueprint": route_info.get("blueprint", ""),
                        }
                    )
                    route_entries.append(route_info)

            if not route_entries or not template_names:
                continue

            for route in route_entries:
                entry = {
                    "file": rel_file,
                    "rule": route["rule"],
                    "methods": route["methods"],
                    "endpoint": route["endpoint"],
                    "template": template_names[0],
                }
                if len(template_names) > 1:
                    entry["templates"] = template_names
                flask_render_routes.append(entry)

    flask_render_routes.sort(
        key=lambda item: (item.get("rule", ""), item.get("endpoint", ""), item.get("template", ""))
    )

    route_collisions_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for entry in all_route_entries:
        rule = str(entry.get("rule", "")).strip()
        endpoint = str(entry.get("endpoint", "")).strip()
        file = str(entry.get("file", "")).strip()
        for method in entry.get("methods", []):
            method_up = str(method or "").strip().upper()
            if not rule or not endpoint or not method_up:
                continue
            route_collisions_map[(rule, method_up)].append(
                {"endpoint": endpoint, "file": file}
            )

    route_collisions: List[Dict[str, Any]] = []
    for (rule, method), items in sorted(route_collisions_map.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if len(items) <= 1:
            continue
        uniq_items: List[Dict[str, str]] = []
        seen = set()
        for item in items:
            key = (item["endpoint"], item["file"])
            if key in seen:
                continue
            seen.add(key)
            uniq_items.append(item)
        if len(uniq_items) <= 1:
            continue
        route_collisions.append(
            {
                "rule": rule,
                "method": method,
                "count": len(uniq_items),
                "endpoints": uniq_items,
            }
        )

    endpoint_set = {str(item.get("endpoint", "")) for item in all_route_entries if item.get("endpoint")}
    endpoint_set.add("static")
    broken_url_for_set: Set[Tuple[str, str]] = set()
    for rel_template in templates_files:
        text = _read_text(templates_dir / rel_template)
        for match in URL_FOR_RE.finditer(text):
            endpoint = (match.group(1) or "").strip()
            if not endpoint or endpoint == "static" or endpoint.startswith("."):
                continue
            if endpoint not in endpoint_set:
                broken_url_for_set.add((rel_template, endpoint))

    broken_url_for = [
        {"template": template, "endpoint": endpoint}
        for template, endpoint in sorted(broken_url_for_set, key=lambda item: (item[0], item[1]))
    ]

    # Heuristic: ignore partial/include folders and private templates in orphan detection.
    orphan_templates = [
        name
        for name in templates_files
        if name not in referenced_templates
        and not name.startswith("partials/")
        and not name.startswith("parts/")
        and not name.startswith("widgets/")
        and not Path(name).name.startswith("_")
    ]

    tmp_path = (project_root / TMP_UI_SERVER_REL).resolve()
    tmp_exists = tmp_path.is_file()

    report: Dict[str, Any] = {
        "generated_at": _iso_now(),
        "project_root": str(project_root.resolve()),
        "templates_files": templates_files,
        "flask_render_routes": flask_render_routes,
        "flask_routes": sorted(
            all_route_entries,
            key=lambda item: (item.get("rule", ""), item.get("endpoint", "")),
        ),
        "route_collisions": route_collisions,
        "orphan_templates": sorted(orphan_templates),
        "missing_templates": sorted(missing_templates_set),
        "portal_guess": portal_guess,
        "broken_url_for": broken_url_for,
        "fastapi_template_violations": sorted(
            fastapi_template_violations,
            key=lambda item: (item.get("file", ""), int(item.get("line", 0))),
        ),
        "parse_errors": sorted(parse_errors, key=lambda item: item.get("file", "")),
        "portal_url": "/admin/portal",
        "tmp_file_guard": {
            "path": str(tmp_path),
            "exists": tmp_exists,
        },
    }
    return report


def _render_routes_lines(routes: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for route in routes:
        methods = ",".join(route.get("methods", []))
        rule = route.get("rule", "")
        endpoint = route.get("endpoint", "")
        template = route.get("template", "")
        out.append(f"- `{methods} {rule}` -> `{template}` (`{endpoint}`)")
    if not out:
        out.append("- (net)")
    return out


def _render_pair_lines(items: Sequence[Dict[str, Any]], left: str, right: str) -> List[str]:
    if not items:
        return ["- (net)"]
    out: List[str] = []
    for item in items:
        out.append(f"- `{item.get(left, '')}` -> `{item.get(right, '')}`")
    return out


def render_markdown(report: Dict[str, Any]) -> str:
    templates_count = len(report.get("templates_files", []))
    routes_count = len(report.get("flask_render_routes", []))
    all_routes_count = len(report.get("flask_routes", []))
    missing_count = len(report.get("missing_templates", []))
    orphan_count = len(report.get("orphan_templates", []))
    broken_count = len(report.get("broken_url_for", []))
    fastapi_violations = len(report.get("fastapi_template_violations", []))
    collisions_count = len(report.get("route_collisions", []))
    tmp_guard = report.get("tmp_file_guard", {})
    tmp_exists = bool(tmp_guard.get("exists"))

    lines: List[str] = []
    lines.append("# UI Report")
    lines.append("")
    lines.append(f"Generated: `{report.get('generated_at', '')}`")
    lines.append(f"Portal template guess: `{report.get('portal_guess') or '(not found)'}`")
    lines.append(f"Canonical portal URL: `{report.get('portal_url', '/admin/portal')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- templates found: `{templates_count}`")
    lines.append(f"- flask routes scanned: `{all_routes_count}`")
    lines.append(f"- flask render routes: `{routes_count}`")
    lines.append(f"- orphan templates: `{orphan_count}`")
    lines.append(f"- missing templates: `{missing_count}`")
    lines.append(f"- route collisions: `{collisions_count}`")
    lines.append(f"- broken url_for entries: `{broken_count}`")
    lines.append(f"- fastapi template violations: `{fastapi_violations}`")
    lines.append(f"- tmp ui server file exists: `{int(tmp_exists)}`")
    lines.append("")
    lines.append("## Routes -> Templates")
    lines.extend(_render_routes_lines(report.get("flask_render_routes", [])))
    lines.append("")
    lines.append("## Orphan Templates (Heuristic)")
    orphans = report.get("orphan_templates", [])
    if orphans:
        lines.extend([f"- `{item}`" for item in orphans])
    else:
        lines.append("- (net)")
    lines.append("")
    lines.append("## Missing Templates")
    missing = report.get("missing_templates", [])
    if missing:
        lines.extend([f"- `{item}`" for item in missing])
    else:
        lines.append("- (net)")
    lines.append("")
    lines.append("## Broken url_for (Heuristic)")
    lines.extend(_render_pair_lines(report.get("broken_url_for", []), "template", "endpoint"))
    lines.append("")
    lines.append("## Route Collisions")
    collisions = report.get("route_collisions", [])
    if collisions:
        for col in collisions:
            lines.append(f"- `{col.get('method', '')} {col.get('rule', '')}` count=`{col.get('count', 0)}`")
            for ep in col.get("endpoints", []):
                lines.append(f"  - `{ep.get('endpoint', '')}` in `{ep.get('file', '')}`")
    else:
        lines.append("- (net)")
    lines.append("")
    lines.append("## FastAPI Guard")
    if report.get("fastapi_template_violations"):
        for item in report.get("fastapi_template_violations", []):
            lines.append(
                f"- `{item.get('file', '')}:{item.get('line', 0)}` -> `{item.get('template', '')}` ({item.get('reason', '')})"
            )
    else:
        lines.append("- FastAPI-moduli ne renderyat Flask templates (evristika).")
    lines.append("")
    lines.append("## Parse Errors")
    if report.get("parse_errors"):
        for item in report.get("parse_errors", []):
            lines.append(f"- `{item.get('file', '')}`: `{item.get('error', '')}`")
    else:
        lines.append("- (net)")
    lines.append("")
    lines.append("## Tmp File Guard")
    lines.append(f"- path: `{tmp_guard.get('path', '')}`")
    lines.append(f"- exists: `{int(tmp_exists)}`")
    if tmp_exists:
        lines.append("- status: FAIL (temporary UI server file must not exist)")
    else:
        lines.append("- status: OK")
    lines.append("")

    smoke = report.get("ui_http_smoke")
    if isinstance(smoke, list):
        lines.append("## HTTP Smoke")
        lines.append(SMOKE_SECTION_BEGIN)
        if smoke:
            for item in smoke:
                path = item.get("path", "")
                status = item.get("status", "ERR")
                final_url = item.get("final_url", "")
                redirect = "yes" if item.get("redirected") else "no"
                error = item.get("error")
                tail = f" error={error}" if error else ""
                lines.append(f"- `{path}` status=`{status}` redirected=`{redirect}` final=`{final_url}`{tail}")
        else:
            lines.append("- (net dannykh)")
        lines.append(SMOKE_SECTION_END)
        lines.append("")

    lines.append("## Bridges")
    lines.append(
        "- Ashby (yavnyy): diagnostika marshrutov/shablonov daet nablyudaemoe i upravlyaemoe raznoobrazie UI."
    )
    lines.append(
        "- Enderton (skrytyy): chastichnaya funktsiya `template -> route` priblizhaetsya k totalnoy za schet ustraneniya neopredelennostey."
    )
    lines.append(
        "- Guyton/Hall (skrytyy): vmesto 500 stranitsy vozvraschayut sostoyanie \"not ready\", sokhranyaya homeostasis kontura."
    )
    lines.append("")
    lines.append("## Earth Paragraph")
    lines.append(
        "UI zdes kak provodka v schitke: poka ne prozvonili klemmy testerom (diagnostika+smoke), nelzya podklyuchat novye avtomaty."
    )
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    report: Dict[str, Any],
    *,
    json_path: Path,
    md_path: Path,
) -> None:
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Static diagnostics for templates and Flask routes.")
    parser.add_argument("--project", default=".", help="Project root path.")
    parser.add_argument("--json-out", default="ui_report.json", help="Output JSON report path.")
    parser.add_argument("--md-out", default="UI_REPORT.md", help="Output Markdown report path.")
    args = parser.parse_args(argv)

    root = Path(args.project).resolve()
    json_out = (root / args.json_out).resolve()
    md_out = (root / args.md_out).resolve()

    report = analyze_project(root)
    write_outputs(report, json_path=json_out, md_path=md_out)

    missing = len(report.get("missing_templates", []))
    parse_errors = len(report.get("parse_errors", []))
    collisions = len(report.get("route_collisions", []))
    tmp_exists = bool((report.get("tmp_file_guard") or {}).get("exists"))
    print("UI_DIAG_OK")
    print(f"templates={len(report.get('templates_files', []))}")
    print(f"flask_routes={len(report.get('flask_routes', []))}")
    print(f"flask_render_routes={len(report.get('flask_render_routes', []))}")
    print(f"missing_templates={missing}")
    print(f"route_collisions={collisions}")
    print(f"parse_errors={parse_errors}")
    print(f"tmp_ui_server_exists={int(tmp_exists)}")
    print(f"json={json_out}")
    print(f"md={md_out}")
    if tmp_exists:
        print("TMP_UI_SERVER_GUARD_FAIL")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
