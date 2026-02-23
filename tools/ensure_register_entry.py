# tools/ensure_register_entry.py
# -*- coding: utf-8 -*-
"""
Ensure every routes-module has an entrypoint for the registrar.

Bridges:
- Explicit: (Loader <-> Compat) adds a tiny register() shim when needed.
- Hidden #1: (Flask <-> FastAPI) supports Blueprint/APIRouter patterns.
- Hidden #2: (Auto-Discover <-> Transparency) prints and writes a JSON report.

Ground paragraph:
Think of it like crimping a connector: if the module exposes routes but
lacks a standard entry, we add a minimal register(app) without touching logic.

c=a+b
"""
from __future__ import annotations
import sys, re, json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BP_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*Blueprint\s*\(', re.M)
ROUTER_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*APIRouter\s*\(', re.M)
HAS_REGISTER_RE = re.compile(r'^\s*def\s+register\s*\(\s*app\s*\)\s*:', re.M)

def strip_bom_and_smart(text: str) -> Tuple[str, bool]:
    changed = False
    # strip BOM if present in Python string
    if text and text[0] == "\ufeff":
        text = text[1:]; changed = True
    before = text
    text = (text.
            replace("\u2014", "-").replace("\u2013","-").replace("\u00A0"," ").
            replace("\u201c", '"').replace("\u201d", '"').
            replace("\u2018","'").replace("\u2019","'"))
    if text != before:
        changed = True
    return text, changed

def ensure_register(glob_path: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "root": str(glob_path.resolve()),
        "processed": 0,
        "patched": 0,
        "shim_flask": 0,
        "shim_fastapi": 0,
        "kept": 0,
        "files": [],
    }

    for p in sorted(glob_path.rglob("*.py")):
        name = p.name
        if name in {"__init__.py", "_safe_loader.py"}:
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            report["files"].append({"file": str(p), "error": f"read_failed: {e}"})
            continue

        report["processed"] += 1
        orig = raw
        raw, changed = strip_bom_and_smart(raw)

        has_register = bool(HAS_REGISTER_RE.search(raw))
        bp_var: Optional[str] = None
        rt_var: Optional[str] = None

        m_bp = BP_RE.search(raw)
        if m_bp:
            bp_var = m_bp.group(1)
        else:
            m_rt = ROUTER_RE.search(raw)
            if m_rt:
                rt_var = m_rt.group(1)

        shim_added = False
        if not has_register:
            if bp_var:
                raw += (
                    "\n\n"
                    "def register(app):\n"
                    f"    app.register_blueprint({bp_var})\n"
                    "    return app\n"
                )
                shim_added = True
                report["shim_flask"] += 1
            elif rt_var:
                raw += (
                    "\n\n"
                    "def register(app):\n"
                    f"    app.include_router({rt_var})\n"
                    "    return app\n"
                )
                shim_added = True
                report["shim_fastapi"] += 1

        if (raw != orig) or shim_added or changed:
            try:
                p.write_text(raw, encoding="utf-8", newline="\n")
            except Exception as e:
                report["files"].append({"file": str(p), "error": f"write_failed: {e}"})
                continue
            report["patched"] += 1
            report["files"].append({"file": str(p), "patched": True, "bp": bp_var, "router": rt_var})
            print("[patched]", p)
        else:
            report["kept"] += 1
            report["files"].append({"file": str(p), "patched": False, "bp": bp_var, "router": rt_var})

    return report

def main() -> None:
    # Po umolchaniyu — katalog routes/ v korne proekta
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("routes")
    if not root.exists():
        print(f"[warn] path not found: {root.resolve()}")
        sys.exit(1)

    rep = ensure_register(root)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    # Polozhim otchet ryadom
    try:
        (Path(".") / "ensure_register_entry.report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass

if __name__ == "__main__":
    main()