# -*- coding: utf-8 -*-
from __future__ import annotations

import os, sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(r"<repo-root>").resolve()
sys.path.insert(0, str(ROOT))

try:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
except Exception:
    chromadb = None  # type: ignore
    Settings = None  # type: ignore

def _cands():
    out = []
    out.append(ROOT)
    for env in ("CHROMA_PERSIST_DIR","ESTER_VSTORE_ROOT","ESTER_HOME","ESTER_STATE_DIR"):
        v = (os.getenv(env,"") or "").strip()
        if v:
            out.append(Path(v))
            out.append(Path(v) / "chroma")
            out.append(Path(v) / "vstore" / "chroma")
    # tipichnye
    out.append(ROOT / "vstore" / "chroma")
    out.append(ROOT / "data" / "vstore" / "chroma")
    # uniq existing dirs
    uniq = []
    seen = set()
    for p in out:
        try:
            p = p.resolve()
        except Exception:
            continue
        if p.exists() and p.is_dir() and str(p) not in seen:
            uniq.append(p); seen.add(str(p))
    return uniq

def _find_sqlite(roots):
    hits = []
    for r in roots:
        try:
            for p in r.rglob("chroma.sqlite3"):
                hits.append(p.parent)
        except Exception:
            pass
    # uniq
    uniq = []
    seen = set()
    for h in hits:
        h = h.resolve()
        if str(h) not in seen:
            uniq.append(h); seen.add(str(h))
    return uniq

def main():
    roots = _cands()
    dirs = _find_sqlite(roots)
    print("CHROMA LOCATOR")
    if chromadb is None:
        print("chromadb not installed -> cannot inspect collections")
        for d in dirs:
            print(" -", d)
        return

    if not dirs:
        print("No chroma.sqlite3 found under candidates.")
        return

    for d in dirs[:20]:
        print("\nDIR:", d)
        try:
            client = chromadb.PersistentClient(path=str(d), settings=Settings(anonymized_telemetry=False))
            cols = client.list_collections()
            if not cols:
                print("  collections: []")
                continue
            for c in cols:
                try:
                    name = getattr(c, "name", None) or str(c)
                    coll = client.get_collection(name=name)
                    cnt = coll.count()
                    print("  -", name, "count=", cnt)
                except Exception as e:
                    print("  -", getattr(c, "name", str(c)), "err=", e)
        except Exception as e:
            print("  open err:", e)

if __name__ == "__main__":
    main()