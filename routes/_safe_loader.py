import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Any

from flask import Blueprint
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _parse_ok(p: Path) -> bool:
    try:
        ast.parse(p.read_text(encoding="utf-8", errors="ignore"), filename=str(p))
        return True
    except Exception:
        return False

def _import_module_from_path(path: Path, mod_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {path}")
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m

def _try_register(app, mod: ModuleType, taken_bp_names: set, report: Dict[str, Any]) -> bool:
    """
    Strategiya registratsii:
      1) esli est Blueprint v atributakh ('bp' ili 'blueprint') — registriruem,
         no esli imya Blueprint uzhe zanyato — propuskaem (karantin duplicate_bp).
      2) inache esli est funktsiya register(app) — vyzyvaem ee.
      3) inache — no_entry.
    """
    bp = None
    for attr in ("bp", "blueprint"):
        candidate = getattr(mod, attr, None)
        if isinstance(candidate, Blueprint):
            bp = candidate
            break

    if bp is not None:
        if bp.name in taken_bp_names:
            report["skipped"]["duplicate_bp"].append(f"{mod.__name__}:{bp.name}")
            return False
        app.register_blueprint(bp)
        taken_bp_names.add(bp.name)
        report["registered"].append(f"{mod.__name__}#{bp.name}")
        return True

    reg = getattr(mod, "register", None)
    if callable(reg):
        try:
            reg(app)
            report["registered"].append(f"{mod.__name__}.register()")
            return True
        except Exception as e:
            report["skipped"]["import"].append(f"{mod.__name__}: register() failed: {repr(e)}")
            return False

    report["skipped"]["no_entry"].append(mod.__name__)
    return False


def boot_register_all(app) -> Dict[str, Any]:
    root = Path(app.config.get("ESTER_ROOT"))
    routes_dir = root / "routes"
    report: Dict[str, Any] = {
        "registered": [],
        "skipped": {"syntax": [], "import": [], "duplicate_bp": [], "no_entry": []},
        "root": str(root),
    }

    # Minimalnye vstroennye (zdorove i koren), chtoby vsegda byl 200
    try:
        from .health_routes import bp as health_bp
        app.register_blueprint(health_bp)
        report["registered"].append("routes.health_routes#health")
    except Exception as e:
        report["skipped"]["import"].append(f"routes.health_routes: {repr(e)}")

    try:
        from .root_minimal import bp as root_bp
        app.register_blueprint(root_bp)
        report["registered"].append("routes.root_minimal#ui_min")
    except Exception as e:
        report["skipped"]["import"].append(f"routes.root_minimal: {repr(e)}")

    taken_bp_names = set(bp.name for bp in app.blueprints.values())

    # Perebor vsekh *.py v routes/, isklyuchaya sluzhebnye
    if routes_dir.exists():
        for p in sorted(routes_dir.glob("*.py")):
            if p.name in ("__init__.py", "_safe_loader.py", "health_routes.py", "root_minimal.py"):
                continue
            mod_name = f"ester.routes.{p.stem}"
            # 1) bystryy otsev po sintaksisu
            if not _parse_ok(p):
                report["skipped"]["syntax"].append(p.name)
                continue
            # 2) popytka importa
            try:
                mod = _import_module_from_path(p, mod_name)
            except Exception as e:
                report["skipped"]["import"].append(f"{p.name}: {repr(e)}")
                continue
            # 3) popytka registratsii
            _try_register(app, mod, taken_bp_names, report)

    # Sokhranyaem otchet na disk
    try:
        import json
        (root / "ester_boot_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return report