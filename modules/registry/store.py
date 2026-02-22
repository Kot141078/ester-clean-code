# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.registry.store — faylovyy JSON‑reestr.
Mosty:
- Yavnyy: get/put/list/search v papke `data/registry/` (ili ENV `ESTER_REGISTRY_DIR`).
- Skrytyy #1: (DX ↔ Stabilnost) — atomarnaya zapis cherez vremennyy fayl i rename.
- Skrytyy #2: (Sovmestimost ↔ Porty) — tolko standartnaya biblioteka, bez vneshnikh zavisimostey.

Zemnoy abzats:
Faylovyy reestr — inzhenernyy «bufer obmena» mezhdu podsistemami: deshevyy, ponyatnyy, nadezhnyy.
# c=a+b
"""
import json, os, tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def base_dir() -> Path:
    root = Path(os.getenv("ESTER_REGISTRY_DIR", "data/registry"))
    root.mkdir(parents=True, exist_ok=True)
    return root

def _ns_dir(ns: str) -> Path:
    d = base_dir() / ns
    d.mkdir(parents=True, exist_ok=True)
    return d

def _path(ns: str, name: str) -> Path:
    return _ns_dir(ns) / f"{name}.json"

def put(ns: str, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    p = _path(ns, name)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="reg_", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, p)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
    return {"ok": True, "path": str(p)}

def get(ns: str, name: str) -> Optional[Dict[str, Any]]:
    p = _path(ns, name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def list_names(ns: str) -> List[str]:
    d = _ns_dir(ns)
    return sorted([p.stem for p in d.glob("*.json")])

def search(ns: str, needle: str) -> List[str]:
    needle = needle.lower()
    return [n for n in list_names(ns) if needle in n.lower()]