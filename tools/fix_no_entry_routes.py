# -*- coding: utf-8 -*-
"""tools/fix_no_entry_routes.py - avto-dobavlenie bezopasnykh vkhodov register(app) dlya marshrutov bez tochek registratsii.

Mosty
- Yavnyy: (Flask/FastAPI ↔ Routy) — unifitsiruem kontrakt podklyucheniy cherez edinyy register(app).
- Skrytyy #1: (Infoteoriya ↔ Inzheneriya) — snizhaem entropiyu interfeysov: odna tochka vkhoda vmesto mnozhestva variantov.
- Skrytyy #2: (Kibernetika Ashbi ↔ Ustoychivost) - add “raznoobrazie adapterov”, chtoby sistema pogloschala razlichiya moduley.

Zemnoy abzats
Kak v santekhnike: esli u tebya truby raznykh standartov, stavish perekhodnik. Zdes takim “perekhodnikom” sluzhit korotkaya funktsiya register(app), kotoraya libo registriruet suschestvuyuschiy bp/router, libo vyzyvaet register_*_routes(...), libo stavit vremennuyu zaglushku do poyavleniya realnoy logiki.

c=a+b"""
from __future__ import annotations
import os, re, sys, shutil
from pathlib import Path
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# List of modules from your report skipped.no_entry (basenate file without .po)
TARGETS = [
    "admin_p2p",
    "beacons_routes",
    "computer_use_anchor_curator",
    "computer_use_macro",
    "computer_use_recorder",
    "computer_use_replay",
    "computer_use_visual_anchor",
    "dreams_routes",
    "email_routes",
    "empathy_routes",
    "feed_routes",
    "forms_routes",
    "ingest_routes",
    "init",
    "mem_kg_routes",
    "p2p_crdt_routes",
    "providers_routes",
    "register_ui",
    "replication_routes",
    "research_routes",
    "routes_rules",
    "scheduler_routes",
    "security_middleware",
    "share_bridge_routes",
    "sources_routes",
    "telegram_routes",
    "telegram_sync",
    "test_research_routes",
]

# Where to look: first rutes/, then ESTER/rutes/ (just in case)
def find_route_file(root: Path, name: str) -> Optional[Path]:
    cands = [
        root / "routes" / f"{name}.py",
        root / "ESTER" / "routes" / f"{name}.py",
        root / "ester" / "routes" / f"{name}.py",
    ]
    for p in cands:
        if p.is_file():
            return p
    return None

AUTOSHIM_HEADER = "\n\n# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===\n"
AUTOSHIM_FOOTER = "\n# === /AUTOSHIM ===\n"

def has_register(text: str) -> bool:
    return re.search(r"^\s*def\s+register\s*\(\s*app\s*\)\s*:", text, re.M) is not None

def has_bp(text: str) -> bool:
    return re.search(r"^\s*bp\s*=\s*Blueprint\(", text, re.M) is not None

def has_router(text: str) -> bool:
    return re.search(r"^\s*router\s*=\s*APIRouter\(", text, re.M) is not None

def find_register_func_name(text: str) -> Optional[str]:
    """We are looking for function-inputs of the form: def register_xxx_rutes(app, ...
    We take the first suitable one - this is enough for the shim."""
    m = re.search(r"^\s*def\s+(register_[A-Za-z0-9_]+_routes)\s*\(\s*app\b", text, re.M)
    return m.group(1) if m else None

def build_shim_for_bp_router(module_name: str) -> str:
    return AUTOSHIM_HEADER + (
        "def register(app):\n"
        "    try:\n"
        "        app.register_blueprint(bp)\n"
        "        return True\n"
        "    except NameError:\n"
        "        pass\n"
        "    try:\n"
        "        app.include_router(router)\n"
        "        return True\n"
        "    except Exception:\n"
        "        pass\n"
        "    return False\n"
    ) + AUTOSHIM_FOOTER

def build_shim_for_register_func(func_name: str) -> str:
    return AUTOSHIM_HEADER + (
        f"def register(app):\n"
        f"# calls an existing ZZF0Z(app) (url_prefix is ​​taken by default inside the function)"
        f"    return {func_name}(app)\n"
    ) + AUTOSHIM_FOOTER

def build_noop_shim(module_name: str) -> str:
    return AUTOSHIM_HEADER + (
        f"# stub for ZZF0Z: no power supply/router/register_*_rutes yet"
        f"def register(app):\n"
        f"    return True\n"
    ) + AUTOSHIM_FOOTER

def process_file(path: Path, dry: bool = False) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if has_register(text):
        return f"[skip] {path} — register(app) uzhe est"

    # priority: yavnyy bp/router → obertka; inache ischem register*routes; different noop
    if has_bp(text) or has_router(text):
        shim = build_shim_for_bp_router(path.stem)
    else:
        func = find_register_func_name(text)
        if func:
            shim = build_shim_for_register_func(func)
        else:
            # the file is empty or service - set noop
            shim = build_noop_shim(path.stem)

    if dry:
        return f"[dry]  {path} — dobavil by AUTOSHIM"

    # backup
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copyfile(path, bak)

    # zapisyvaem
    with open(path, "a", encoding="utf-8") as f:
        f.write(shim)
    return f"[fix]  {path} — dobavlen AUTOSHIM"

def main():
    root = Path(__file__).resolve().parents[1]
    dry = ("--dry" in sys.argv)

    print(f"[info] project root: {root}")
    print(f"[info] mode: {'DRY-RUN' if dry else 'APPLY'}")
    total = 0
    fixed = 0

    for name in TARGETS:
        p = find_route_file(root, name)
        total += 1
        if not p:
            print(f"[miss] {name}.py — fayl ne nayden v routes/ ili ESTER/routes/")
            continue
        try:
            msg = process_file(p, dry=dry)
            if msg.startswith("[fix]"):
                fixed += 1
            print(msg)
        except Exception as e:
            print(f"[err]  {p}: {e}")

    print(f"[done] processed={total}, fixed={fixed}, dry={dry}")

if __name__ == "__main__":
    main()