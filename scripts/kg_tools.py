# -*- coding: utf-8 -*-
"""scripts/kg_tools.py - universalnyy CLI dlya KG: export/import/repair/neighbors.

Primery:
  # Eksport grafa v fayl
  python -m scripts.kg_tools export --out /tmp/kg.json

  # Import (replace)
  python -m scripts.kg_tools import --in /tmp/kg.json --policy replace

  # Repair
  python -m scripts.kg_tools repair

  #Neighbours
  python -m scripts.kg_tools neighbors --id topic::ocr --json"""

from __future__ import annotations

import argparse
import json
import os
import sys

from memory.kg_store import KGStore  # drop-in
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def cmd_export(args) -> int:
    kg = KGStore()
    g = kg.export_all()
    if args.out:
        _write_json(args.out, g)
        print(f"OK: exported nodes={len(g['nodes'])} edges={len(g['edges'])} -> {args.out}")
    else:
        print(json.dumps(g, ensure_ascii=False, indent=2))
    return 0


def cmd_import(args) -> int:
    kg = KGStore()
    g = _read_json(args.infile)
    policy = args.policy.lower()
    if policy not in ("merge", "replace"):
        print("policy must be merge|replace", file=sys.stderr)
        return 2
    res = kg.import_graph({"nodes": g.get("nodes", []), "edges": g.get("edges", [])}, policy=policy)
    print(json.dumps({"ok": True, **res}, ensure_ascii=False, indent=2))
    return 0


def cmd_repair(args) -> int:
    kg = KGStore()
    rep = kg.repair()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


def cmd_neighbors(args) -> int:
    kg = KGStore()
    data = kg.neighbors(args.id, rel=args.rel)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        node = data["node"]
        outs = data["out"]
        ins = data["in"]
        print(f"Node: {node['id']} ({node.get('label','')})")
        print(f"Out edges: {len(outs)}")
        for e in outs:
            print(f"  {e['src']} -[{e['rel']}:{e['weight']:.2f}]-> {e['dst']}")
        print(f"In edges: {len(ins)}")
        for e in ins:
            print(f"  {e['src']} -[{e['rel']}:{e['weight']:.2f}]-> {e['dst']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="KG tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("export", help="Eksport grafa")
    p_exp.add_argument(
        "--out", type=str, default=None, help="The way to save ZhSON"
    )
    p_exp.set_defaults(func=cmd_export)

    p_imp = sub.add_parser("import", help="Import grafa iz fayla")
    p_imp.add_argument("--in", dest="infile", type=str, required=True)
    p_imp.add_argument("--policy", type=str, default="merge", help="merge|replace")
    p_imp.set_defaults(func=cmd_import)

    p_rep = sub.add_parser("repair", help="Repair KG")
    p_rep.set_defaults(func=cmd_repair)

    p_nb = sub.add_parser("neighbors", help="Okrestnost uzla")
    p_nb.add_argument("--id", type=str, required=True)
    p_nb.add_argument("--rel", type=str, default=None)
    p_nb.add_argument("--json", action="store_true")
    p_nb.set_defaults(func=cmd_neighbors)

    args = p.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())