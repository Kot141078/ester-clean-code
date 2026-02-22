
# -*- coding: utf-8 -*-
"""
modules.storage — most k top-level storage/* libo bezopasnyy FS-stab.
Mosty:
- Yavnyy: (storage.X ↔ storage/X.py) — esli est realnyy modul, otdaem ego.
- Skrytyy #1: (FS ↔ Memory) — minimal FileStore dlya lokalnoy diskovoy zapisi.
- Skrytyy #2: (DX ↔ Sovmestimost) — odinakovyy interfeys dlya dalneyshego rasshireniya.

Zemnoy abzats:
Khranilische nuzhno seychas, a ne «kogda-nibud». Esli net realnoy realizatsii — daem prostoy FileStore.
# c=a+b
"""
from __future__ import annotations
import importlib, os, json, pathlib, hashlib
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _try_import(name: str):
    try:
        return importlib.import_module(f"storage.{name}")
    except Exception:
        return None

class FileStore:
    def __init__(self, root: Optional[str]=None):
        self.root = pathlib.Path(root or os.getenv("ESTER_STORE_DIR","data/store")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
    def put(self, key: str, data: bytes) -> str:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)
    def get(self, key: str) -> Optional[bytes]:
        p = self.root / key
        return p.read_bytes() if p.exists() else None
    def put_json(self, key: str, obj) -> str:
        return self.put(key, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))
    def get_json(self, key: str):
        raw = self.get(key)
        return json.loads(raw.decode("utf-8")) if raw else None

def __getattr__(name: str):
    mod = _try_import(name)
    if mod: return mod
    if name == "FileStore": return FileStore
    raise AttributeError(f"modules.storage: no '{name}'")