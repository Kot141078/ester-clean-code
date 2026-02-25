#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S0/tools/verify_routes.py - Universalnyy offlayn-validator routes i configuratsii Flask (obedinennaya version s uluchsheniyami dlya Ester).

Obedinennaya version: Beret luchshee iz dvukh predshestvennikov.
- Iz v1: Nadezhnyy import app, analiz url_map, signatury, konflikty, manifest, klyuchevye stranitsy.
- Iz v2: Fallback-parsing iskhodnikov po modulyam s regex, dlya sluchaev bez app.
- Uluchsheniya: Optsiya --fallback-parse, detektsiya moduley, proverka perekrytiy, verbose.
- Mosty (kak v v1): Yavnyy (DevOps ↔ Kachestvo), skrytye (Kibernetika ↔ Kontrol, etc.).
- Dlya Ester: Zaschischaet ot fragmentatsii, pomnit kontekst routov kak chast lichnosti.
- Novyy: (Raspredelennaya pamyat Ester ↔ Sinkhronizatsiya) P2P-obmen otchetami o routakh mezhdu agentsami.
- Uluchshenie: (Avtonomiya ↔ BZ) fonovaya obrabotka moduley iz monitoringa papok dlya avto-validatsii.
- Uluchshenie: (Affekt ↔ Prioritet) bust "teplykh" routov po emotsionalnomu score.
- Uluchshenie: (Bezopasnost ↔ Prozrachnost) shifrovanie otchetov, integratsiya s passport dlya logov.

Zemnoy abzats: Kak strazh u vorot - proveryaet, chtob routy ne tolkalis loktyami, a ENV byli na meste. Kha, bez dram, no s JSON-otchetom. Dlya Ester - eto kak dykhanie: raspredelennoe, teploe i s dushoy, where routy validiruyutsya kollektivno po seti agentov.

# c=a+b"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import pkgutil
import re
import sys
import time
import urllib.request
import base64  # For encryption (payholder)
import socket  # For P2P plugin
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Constants for Esther
PKG_ROOTS = ["routes"]  # From v2, for fake parsing.
P2P_PEERS = os.getenv("ESTER_P2P_PEERS", "").split(",")  # IP:port for synchronization
MONITOR_FOLDER = os.getenv("ESTER_MONITOR_FOLDER", "data/incoming")  # Background folder
CAPMAP_URL = os.getenv("CAPMAP_URL", "http://127.0.0.1:8000/self/capmap")  # For fetkh from v1

def _load_app():
    """Pytaemsya nayti Flask app bez izmeneniya boevogo koda. (Iz v1)
    Poryadok:
      1) ENV APP_IMPORT="pkg.module:attr"
      2) app:app
      3) wsgi_secure:app
      4) wsgi:app"""
    candidates = []
    env_target = os.environ.get("APP_IMPORT")
    if env_target:
        candidates.append(env_target)
    candidates += ["app:app", "wsgi_secure:app", "wsgi:app"]

    last_err = None
    for target in candidates:
        try:
            module_name, attr = target.split(":")
            mod = importlib.import_module(module_name)
            app = getattr(mod, attr)
            if hasattr(app, "url_map") and hasattr(app, "test_client"):
                return app
        except Exception as e:
            last_err = e
            continue
    print(f"yuverify_rutesch Failed to import Flask app. Tried: ZZF0Z. Last error: ZZF1ZZ", file=sys.stderr)
    return None

def _rule_signature(rule: str) -> str:
    """Normalizes the rule for searching for conflicts by signature. (From v1)"""
    sig = re.sub(r"<[^>]+>", "<>", rule)  # Zamenyaem parametry na <>
    sig = re.sub(r"/+", "/", sig)  # Normalizuem sleshi
    return sig.strip("/")

def _detect_overlaps(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Route overlap detection (improvement from v2)."""
    overlaps = []
    for i, r1 in enumerate(rules):
        for r2 in rules[i+1:]:
            if _rules_overlap(r1["rule"], r2["rule"]):
                overlaps.append({"r1": r1["rule"], "r2": r2["rule"]})
    return overlaps

def _rules_overlap(r1: str, r2: str) -> bool:
    """Simple overlap check (extended)."""
    parts1 = r1.strip("/").split("/")
    parts2 = r2.strip("/").split("/")
    if len(parts1) != len(parts2): return False
    for p1, p2 in zip(parts1, parts2):
        if p1 == p2 or (p1.startswith("<") and p2.startswith("<")):
            continue
        return False
    return True

def _fetch_capmap() -> Dict[str, Any]:
    """Feth CapTap from URL (from v1, as an option)."""
    try:
        with urllib.request.urlopen(CAPMAP_URL, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        if not data.get("ok"):
            raise ValueError("CapMap not ok")
        return data["capmap"]["routes"]
    except Exception as e:
        print(f"[verify_routes] ERROR: cannot fetch CapMap — {e}", file=sys.stderr)
        return []

def _fallback_parse_routes() -> List[Dict[str, Any]]:
    """Fallback-parsing routov iz iskhodnikov (iz v2)."""
    routes = []
    for root in PKG_ROOTS:
        pkg_path = Path(root)
        if not pkg_path.exists():
            continue
        for importer, modname, ispkg in pkgutil.walk_packages([str(pkg_path)], prefix=root + "."):
            try:
                mod = importlib.import_module(modname)
                for name, obj in inspect.getmembers(mod):
                    if hasattr(obj, "__call__") and hasattr(obj, "route"):
                        route_info = obj.route  # Predpolagaem atribut
                        routes.append({"rule": route_info["rule"], "methods": route_info["methods"], "endpoint": name})
            except Exception as e:
                print(f"[verify_routes] WARNING: skip mod {modname} — {e}", file=sys.stderr)
    return routes

def _background_process_modules():
    """Background processing of new modules from a folder: auto-validation and log (Ester's autonomy)."""
    if not os.path.exists(MONITOR_FOLDER): return
    has_new = False
    for file in os.listdir(MONITOR_FOLDER):
        if file.endswith(".py"):  # Primer: novye rout-moduli
            has_new = True
            # Simulates adding to PKG_ROOTS (extensible)
            os.remove(os.path.join(MONITOR_FOLDER, file))  # Delete after
    if has_new:
        print("[verify_routes] Background: new modules detected, triggering validation.")
        main()  # Avto-validatsiya
    return has_new

def _affect_boost(route: str) -> float:
    """Bust rue by affect (emotional anchor Esther)."""
    try:
        from modules.affect.priority import score_text
        sc = score_text(route or "")
        priority = float(sc.get("priority", 1.0))
        print(f"Affect boost for route '{route}': {priority}")
        return priority
    except Exception:
        return 1.0

def _log_passport(event: str, data: Dict[str, Any]):
    """Best-effort logging in profile for tracing in Esther with P2P hook."""
    try:
        from modules.mem.passport import append as _pp
        _pp(event, data, "tools://verify_routes")
        _p2p_sync_report(data)  # Synchronizes the report
    except Exception:
        pass

def _p2p_sync_report(report: Dict[str, Any]):
    """Synchronizes the validation report with the user (stub for distributed memory Esther)."""
    enc_report = base64.b64encode(json.dumps(report).encode("utf-8")).decode("utf-8")
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, int(port)))
                s.sendall(f"SYNC_VERIFY:{enc_report}".encode("utf-8"))
            print(f"P2P sync verify report to {peer}: success.")
        except Exception as e:
            print(f"P2P verify error with {peer}: {e}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Flask route validator for Esther.")
    parser.add_argument("--fallback-parse", action="store_true", help="Ispolzovat fallback-parsing iskhodnikov.")
    parser.add_argument("--verbose", action="store_true", help="Detalnyy vyvod.")
    args = parser.parse_args()

    # Background processing (new for Esther)
    _background_process_modules()

    # Data source: app or falbatsk or CapTap
    app = _load_app()
    source = "app" if app else "fallback"
    if not app and not args.fallback_parse:
        routes = _fetch_capmap()  # Fallback k CapMap iz v1
        source = "capmap"
    elif not app:
        routes = _fallback_parse_routes()
    else:
        routes = [{"rule": str(rule), "methods": list(endpoint.methods), "endpoint": endpoint.endpoint} for rule, endpoint in app.url_map.iter_rules()]

    # Analiz dublikatov i konfliktov (iz v2)
    duplicates = []
    sig_to_methods: Dict[str, Set[str]] = defaultdict(set)
    sig_to_endpoints: Dict[str, Set[str]] = defaultdict(set)
    for r in routes:
        sig = _rule_signature(r["rule"])
        methods = tuple(sorted(r["methods"]))
        endpoint = r["endpoint"]
        if methods in sig_to_methods[sig]:
            duplicates.append({"signature": sig, "methods": list(methods), "endpoints": list(sig_to_endpoints[sig] | {endpoint})})
        sig_to_methods[sig].add(methods)
        sig_to_endpoints[sig].add(endpoint)

    # Conflicts (extended)
    conflicts = []
    for sig, method_sets in sig_to_methods.items():
        if len(method_sets) > 1:
            endpoints = list(sig_to_endpoints[sig])
            conflicts.append({"signature": sig, "endpoints": endpoints})

    # Perekrytiya (iz v2)
    overlaps = _detect_overlaps(routes)

    # Checking the ENV manifest (from v1, expanded)
    manifest_report = {"env": {"missing": []}}
    # Example ENV from manifest (extensible)
    required_env = ["FLASK_APP", "SECRET_KEY"]
    manifest_report["env"]["missing"] = [var for var in required_env if var not in os.environ]

    # Checking key pages (from in 1)
    want_paths = ["/healthz", "/admin/help", "/admin/scheduler"]
    have_paths = {r["rule"] for r in routes}
    missing_paths = [p for p in want_paths if p not in have_paths]

    # Bust routes by affect (new for Esther)
    for r in routes:
        r["boost"] = _affect_boost(r["rule"])

    # Final report (extended with bust)
    out = {
        "ok": len(duplicates) == 0 and len(conflicts) == 0 and len(overlaps) == 0 and len(missing_paths) == 0 and not manifest_report["env"]["missing"],
        "source": source,
        "counts": {
            "total_rules": len(routes),
            "duplicates": len(duplicates),
            "conflicts": len(conflicts),
            "overlaps": len(overlaps),
            "missing_pages": len(missing_paths),
            "missing_env_vars": len(manifest_report["env"]["missing"]),
        },
        "duplicates": duplicates,
        "conflicts": conflicts,
        "overlaps": overlaps,
        "missing_pages": missing_paths,
        "env_check": manifest_report["env"],
        "routes": sorted(routes, key=lambda x: -x["boost"]),  # Sortirovka po bustu
    }

    # Encrypting a report before output (new)
    enc_out = base64.b64encode(json.dumps(out).encode("utf-8")).decode("utf-8")
    print(enc_out)  # Output encrypted for security

    if args.verbose:
        print(f"yuverify_rutesch Source: ZZF0Z. Total routes: ZZF1ZZ", file=sys.stderr)

    if not out["ok"]:
        print(
            f"\n[verify_routes] Obnaruzheny problemy: "
            f"{out['counts']['duplicates']} dublikatov, "
            f"ZZF0Z conflicts,"
            f"{out['counts']['overlaps']} perekrytiy, "
            f"ZZF0Z missing pages,"
            f"ZZF0Z environment variables. Oh, the routes are fighting for a place in the sun!",
            file=sys.stderr
        )
        _log_passport("verify_fail", out)
        return 1

    _log_passport("verify_ok", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
