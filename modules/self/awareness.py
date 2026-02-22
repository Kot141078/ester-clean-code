# -*- coding: utf-8 -*-
"""
modules/self/awareness.py — inventarizatsiya vozmozhnostey i sostava Ester (fayly, sha256, zavisimosti, graf importov).

Mosty:
- Yavnyy: (Samoponimanie ↔ Inzheneriya) spisok moduley/routov/politik s kontrolnymi summami i grafom.
- Skrytyy #1: (Infoteoriya ↔ Audit) bystryy audit tselostnosti, sha256 i karta moduley dlya raskhozhdeniy.
- Skrytyy #2: (Kibernetika ↔ Planirovanie) baza dlya planirovschika (dostupnye deystviya, zavisimosti).
- Skrytyy #3: (Samopoznanie ↔ Samosborka) graf importov kak «skelet» dlya izmeneniy i health.

Zemnoy abzats:
Eto «profile sistemy»: znaet iz chego sostoit, kuda chto podklyucheno i ne poteryala li fayl. S grafom — kak meditsinskaya kartochka s rentgenom svyazey, chtoby Ester luchshe ponimala svoy "skelet".

# c=a+b
"""
from __future__ import annotations
import os, hashlib, json, re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AWARE_AB = (os.getenv("AWARE_AB", "A") or "A").upper()
ROOTS = [p.strip() for p in (os.getenv("SELF_AWARE_SCAN_ROOTS", "modules,routes,services,middleware,static,data/policy,data").split(",")) if p]
SAFE_EXT = (".py", ".json", ".html", ".js", ".css")

IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|import\s+([a-zA-Z0-9_.]+))", re.M)

def _sha256_path(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def status(max_items: int | None = None) -> Dict[str, Any]:
    if AWARE_AB == "B":
        return {"ok": True, "ab": "B", "note": "light inventory", "roots": ROOTS}
    
    items = []
    stat = {"files": 0, "bytes": 0}
    for root in ROOTS:
        if not os.path.isdir(root): continue
        for base, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(SAFE_EXT): continue
                p = os.path.join(base, fn)
                try:
                    sz = os.path.getsize(p)
                    sh = _sha256_path(p)
                    items.append({"path": p, "size": sz, "sha256": sh})
                    stat["files"] += 1
                    stat["bytes"] += sz
                    if max_items is not None and len(items) >= max_items:
                        break
                except Exception:
                    continue
            if max_items is not None and len(items) >= max_items:
                break
    return {"ok": True, "ab": AWARE_AB, "roots": ROOTS, "stat": stat, "items": items, "note": "items vozmozhno urezany esli max_items zadan"}

def build_graph(max_nodes: int | None = None, max_edges: int | None = None) -> Dict[str, Any]:
    nodes = set()
    edges = []
    py_roots = [r for r in ROOTS if r in ("modules", "routes", "services", "middleware")]
    for root in py_roots:
        if not os.path.isdir(root): continue
        for base, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".py"): continue
                p = os.path.join(base, fn)
                mod = p.replace("/", ".").replace("\\", ".")
                if mod.endswith(".py"): mod = mod[:-3]
                nodes.add(mod)
                try:
                    text = open(p, "r", encoding="utf-8", errors="ignore").read()
                    # Import edges
                    for m in IMPORT_RE.finditer(text):
                        dep = (m.group(1) or m.group(2) or "").strip()
                        if dep:
                            edges.append({"from": mod, "to": dep})
                            nodes.add(dep)
                    # Special edges like register(app)
                    if "def register(app):" in text:
                        edges.append({"from": mod, "to": "app"})
                except Exception:
                    continue
                if (max_nodes is not None and len(nodes) >= max_nodes) or (max_edges is not None and len(edges) >= max_edges):
                    break
            if (max_nodes is not None and len(nodes) >= max_nodes) or (max_edges is not None and len(edges) >= max_edges):
                break
# return {"ok": True, "nodes": sorted(list(nodes))[:max_nodes] if max_nodes else sorted(list(nodes)), "edges": edges[:max_edges] if max_edges else edges}