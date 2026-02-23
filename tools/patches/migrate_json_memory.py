# -*- coding: utf-8 -*-
"""
migrate_json_memory.py
Slivaet starye memory.json iz tipichnykh mest v tekuschiy store._FILE (ESTER_STATE_DIR/ESTER_HOME).

Politika sliyaniya:
- klyuch = id
- esli id uzhe est -> berem zapis s bolee novym ts
- vec pereschitaem stabilnym embed (A1), staryy vec sokhranim kak vec_legacy (esli byl)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(r"D:\ester-project").resolve()

def _load_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_json(p: Path, data: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def main() -> None:
    from modules.memory import store
    from modules.memory.vector import embed, normalize_vec

    target = Path(getattr(store, "_FILE", ""))
    if not str(target):
        raise SystemExit("store._FILE not found")

    dim = int(os.getenv("MEM_VEC_DIM", "384").strip() or 384)

    # kandidaty na “staruyu” pamyat
    candidates = [
        ROOT / "data" / "memory" / "memory.json",
    ]

    # plyus: vse memory.json pod proektom (ogranichim glubinu)
    for p in ROOT.rglob("memory.json"):
        if "site-packages" in str(p).lower():
            continue
        candidates.append(p)

    # unikalno
    uniq = []
    seen = set()
    for c in candidates:
        c = c.resolve()
        if c.exists() and str(c) not in seen and c != target.resolve():
            uniq.append(c)
            seen.add(str(c))

    base: Dict[str, Dict[str, Any]] = {}
    if target.exists():
        base = _load_json(target) or {}
        if not isinstance(base, dict):
            base = {}

    merged = 0
    skipped = 0

    for src in uniq:
        data = _load_json(src)
        if not isinstance(data, dict) or not data:
            continue

        for rid, rec in data.items():
            if not isinstance(rec, dict):
                continue
            ts = int(rec.get("ts") or 0)
            old = base.get(rid)
            old_ts = int(old.get("ts") or 0) if isinstance(old, dict) else -1
            if old is not None and ts <= old_ts:
                skipped += 1
                continue

            # pereschet vec (staroe sokhranyaem)
            v = rec.get("vec")
            if isinstance(v, list) and v:
                rec.setdefault("vec_legacy", v)

            txt = str(rec.get("text") or "").strip()
            rec["vec"] = normalize_vec(embed(txt), dim)
            base[rid] = rec
            merged += 1

    _save_json(target, base)
    print("OK: migration done")
    print("TARGET:", str(target))
    print("MERGED:", merged, "SKIPPED:", skipped)
    if uniq:
        print("SOURCES:")
        for s in uniq[:20]:
            print(" -", s)
        if len(uniq) > 20:
            print(" ...", len(uniq)-20, "more")
    else:
        print("No legacy sources found (ok).")

if __name__ == "__main__":
    main()