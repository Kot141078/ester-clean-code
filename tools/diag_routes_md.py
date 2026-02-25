#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tools/diag_routes_md.py - Markdown-damp routes Flask s podsvetkoy konfliktov.

Mosty:
- Yavnyy: Enderton (logika) → marshruty kak predikaty nad (method, path): proveryaemost cherez normalizovannye signatury.
- Skrytyy #1: Ashbi (kibernetika) → regulyator prosche sistemy: odin prokhod po url_map, minimalnaya slozhnost.
- Skrytyy #2: Cover & Thomas (infoteoriya) → snizhenie "entropii" configuratsii: yavnoe vyyavlenie neodnoznachnostey/dublikatov.

Zemnoy abzats (inzheneriya):
Skript importiruet suschestvuyuschiy Flask app (APP_IMPORT=module:attr or avto-poisk app:app / wsgi_secure:app / wsgi:app),
sobiraet kartu routes i pishet chelovekochitaemyy Markdown. Ne menyaet rantaym, bezopasen dlya CI.
A/B-slot: AB_MODE=A (po umolchaniyu) — kratkiy otchet; AB_MODE=B — extended diagramma frequency metodov i JSON-damp.
Esli vyvod v fayl ne udaetsya - avtokatbek na stdout.

# c=a+b"""
from __future__ import annotations
import argparse
import importlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _load_app():
    env_target = os.environ.get("APP_IMPORT")
    candidates = [env_target] if env_target else []
    candidates += ["app:app", "wsgi_secure:app", "wsgi:app"]
    last_err = None
    for target in candidates:
        try:
            module_name, attr = target.split(":")
            mod = importlib.import_module(module_name)
            app = getattr(mod, attr)
            if hasattr(app, "url_map") and hasattr(app, "test_client"):
                return app, target
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise SystemExit(
        f"yudiag_rutes_mdsch Failed to import Flask app. Tried: ZZF0Z."
        f"Last error: ZZF0Z"
    )

def _rule_signature(path: str) -> str:
    # /api/user/<int:id> -> /api/user/{int}
    return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)

def _collect(app, prefix: str | None = None):
    routes: List[Dict[str, Any]] = []
    sig_map: Dict[Tuple[str, str], List[str]] = {}
    methods_hist: Dict[str, int] = {}

    for rule in sorted(app.url_map.iter_rules(), key=lambda r: (r.rule, sorted(r.methods))):
        rule_path = str(rule.rule)
        if prefix and not rule_path.startswith(prefix):
            continue
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        endpoint = rule.endpoint
        sig = (_rule_signature(rule_path), ",".join(methods))
        sig_map.setdefault(sig, []).append(endpoint)
        for m in methods:
            methods_hist[m] = methods_hist.get(m, 0) + 1
        routes.append(
            {
                "rule": rule_path,
                "methods": methods,
                "endpoint": endpoint,
                "signature": sig[0],
            }
        )

    conflicts = []
    for sig, endpoints in sig_map.items():
        if len(endpoints) > 1:
            conflicts.append({"signature": sig[0], "methods": sig[1], "endpoints": endpoints})

    return routes, conflicts, methods_hist

def _render_md(target: str, routes, conflicts, methods_hist, ab_mode: str, verbose: bool) -> str:
    lines: List[str] = []
    lines.append(f"# Flask routes report\n")
    lines.append(f"- Target: `{target}`")
    lines.append(f"- Total routes: **{len(routes)}**")
    lines.append(f"- Potential conflicts: **{len(conflicts)}**")

    if conflicts:
        lines.append("## Conflicts\n")
        for c in conflicts:
            lines.append(f"- `{c['signature']}` — **{c['methods']}** → {', '.join(c['endpoints'])}")
        lines.append("")

    lines.append("## Routes\n")
    lines.append("| Rule | Methods | Endpoint |")
    lines.append("|------|---------|----------|")
    for r in routes:
        methods = ", ".join(r["methods"])
        lines.append(f"| `{r['rule']}` | {methods} | `{r['endpoint']}` |")
    lines.append("")

    if ab_mode == "b":
        lines.append("## Methods histogram\n")
        for m, cnt in sorted(methods_hist.items()):
            lines.append(f"- **{m}**: {cnt}")
        lines.append("")

    if verbose:
        # Additional JSION for machine verification
        blob = {"routes": routes, "conflicts": conflicts, "methods_hist": methods_hist}
        lines.append("## JSON\n")
        lines.append("```json")
        lines.append(json.dumps(blob, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown-damp marshrutov Flask")
    ap.add_argument("--out", default="-", help="Output file or b for stdout")
    ap.add_argument("--prefix", default="", help="Filtr po prefiksu puti (naprimer, /api)")
    args = ap.parse_args()

    app, target = _load_app()
    ab_mode = (os.environ.get("AB_MODE") or "A").strip().lower()
    verbose = (os.environ.get("DIAG_VERBOSE") or "0").strip() in {"1", "true", "yes", "on"}

    routes, conflicts, methods_hist = _collect(app, prefix=(args.prefix or None))
    md = _render_md(target, routes, conflicts, methods_hist, ab_mode, verbose)

    out_path = args.out
    if out_path and out_path != "-":
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"Yudiag_rutes_mdshch Markdovn the report is saved in ZZF0Z (ZZF1ZZ routes).")
        except Exception as e:  # noqa: BLE001
            print(f"yudiag_rutes_mdsch VARN: failed to write file (ZZF0Z). I am typing in stdout.")
            print(md)
    else:
        print(md)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
