# -*- coding: utf-8 -*-
"""
modules/portable/self_build.py — «samosborka» portable-paketa i avto-raskladka faylov.

MOSTY:
- (Yavnyy) build(portable_dir, dry_run=False) — sobiraet perenosimyy distributiv (skripty, env, templates, routes, modules).
- (Skrytyy #1) place_unknown(path) — kuda polozhit «neznakomyy fayl» (evristika po rasshireniyu/soderzhimomu).
- (Skrytyy #2) Uvazhaet peremennye .env (PORTABLE_*), generiruet manifest i khesh-kartu.

ZEMNOY ABZATs:
Eto «chemodanchik s instrumentami»: odnoy komandoy — sobrat perenosimuyu kopiyu i razlozhit naydennoe po polkam.

# c=a+b
"""
from __future__ import annotations
import os, re, io, json, hashlib, zipfile, glob
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DEFAULT_INCLUDE = [
    "app.py", "verify_routes.py", "asgi/**", "routes/**", "modules/**", "templates/**", "static/**", "tools/**", ".env",
]
DEFAULT_EXCLUDE = [".git/**", ".venv/**", "__pycache__/**", "node_modules/**", "*.log", "*.tmp", "*.cache"]

def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def _match_globs(path: str, patterns: List[str]) -> bool:
    from fnmatch import fnmatch
    p = path.replace("\\","/")
    return any(fnmatch(p, pat) for pat in patterns)

def place_unknown(path: str) -> Tuple[str, str]:
    """
    Vozvraschaet (podkatalog v proekte, prichina).
    """
    lower = path.lower()
    try:
        with open(path, "rb") as f:
            head = f.read(2048)
    except Exception:
        head = b""
    if lower.endswith((".py",)):
        return ("modules/misc", "python-module")
    if lower.endswith((".html",".jinja",".htm")):
        return ("templates/misc", "template")
    if lower.endswith((".css",".js",".ts",".tsx",".vue")):
        return ("static/misc", "asset")
    if lower.endswith((".md",".rst",".txt",".pdf",".docx",".rtf",".json",".yaml",".yml")):
        return ("docs/misc", "doc")
    if b"flask" in head or b"fastapi" in head or b"blueprint" in head:
        return ("routes/misc", "route-ish")
    return ("data/extras", "binary/other")

def _gather(include: List[str], exclude: List[str]) -> List[str]:
    res: List[str] = []
    for patt in include:
        for p in glob.glob(patt, recursive=True):
            if os.path.isdir(p): continue
            if _match_globs(p, exclude): continue
            res.append(p)
    return sorted(set(res))

def build(portable_dir: str, dry_run: bool = False) -> Dict[str, Any]:
    os.makedirs(portable_dir, exist_ok=True)
    include = (os.getenv("PORTABLE_INCLUDE","") or "").split(";")
    exclude = (os.getenv("PORTABLE_EXCLUDE",".git,.venv,__pycache__,*.log,*.tmp,*.cache,node_modules").split(","))
    inc = [p for p in DEFAULT_INCLUDE + include if p and p != ""]
    exc = [p.strip() for p in DEFAULT_EXCLUDE + exclude if p and p != ""]
    files = _gather(inc, exc)

    manifest = {"paths": [], "ts": __import__("time").time(), "why": {}}
    hashes: Dict[str,str] = {}
    for p in files:
        hashes[p] = _hash_file(p)
        manifest["paths"].append(p)

    # Pakuem v zip
    name = f"portable_{int(manifest['ts'])}.zip"
    zpath = os.path.join(portable_dir, name)
    if not dry_run:
        with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for p in files:
                zf.write(p, p.replace("\\","/"))
            zf.writestr("PORTABLE.MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("PORTABLE.HASHMAP.json", json.dumps(hashes, ensure_ascii=False, indent=2))

    return {
        "ok": True, "zip": (name if not dry_run else None),
        "count": len(files), "dir": portable_dir,
        "dry_run": dry_run, "hashes": list(hashes.items())[:8]  # prevyu
    }
# c=a+b