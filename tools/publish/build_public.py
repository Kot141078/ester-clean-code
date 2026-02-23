# -*- coding: utf-8 -*-
"""
tools/publish/build_public.py — sborka «public-safe» eksporta proekta.

MOSTY:
- (Yavnyy) build_public(dry_run=True|False) — formiruet ochischennuyu kopiyu + ZIP.
- (Skrytyy #1) A/B-sloty sanitizatsii: A (umerennaya, po umolchaniyu), B (strogaya cherez SANITIZE_STRICT=1).
- (Skrytyy #2) Avtokatbek: pri provale strogoy — avtomaticheski probuem slot A.

ZEMNOY ABZATs:
Pakuem akkuratnyy chemodan: iskhodniki i shablony ostayutsya, sekrety — v chekhle, lichnoe — doma.

# c=a+b
"""
from __future__ import annotations
import os, io, json, time, shutil, zipfile, re, glob
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

EXPORT_DIR = "data/public_export"

def _load_manifest() -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
        with open("config/public_manifest.yaml","r",encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # bezopasnyy defolt
        return {
            "include": ["app.py","asgi/**","routes/**","modules/**","templates/**","static/**","tools/**","verify_routes.py","README*.md","LICENSE*"],
            "exclude": [".git/**",".venv/**","__pycache__/**","node_modules/**","data/**","logs/**","state/**","*.log","*.tmp","*.cache","**/*.pyc"],
            "redact_env": True
        }

def _gather(include: List[str], exclude: List[str]) -> List[str]:
    from fnmatch import fnmatch
    res = []
    all_paths = set()
    for patt in include:
        for p in glob.glob(patt, recursive=True):
            if os.path.isdir(p): continue
            all_paths.add(p.replace("\\","/"))
    for p in sorted(all_paths):
        skip = any(fnmatch(p, ex) for ex in exclude)
        if not skip:
            res.append(p)
    return res

def _write_file(dst_root: str, src_path: str):
    dst_path = os.path.join(dst_root, src_path)
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_path, dst_path)

def _make_env_public(dst_root: str, slot: str):
    """
    Pishem .env.public s redaktirovaniem klyuchey. Lokalnyy .env ne trogaem.
    """
    src = ".env"
    dst_public = os.path.join(dst_root, ".env.public")
    lines_out: List[str] = []
    if os.path.isfile(src):
        with open(src,"r",encoding="utf-8",errors="ignore") as f:
            for line in f:
                if re.match(r"^\s*#", line): 
                    lines_out.append(line); continue
                m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
                if not m:
                    lines_out.append(line); continue
                k, v = m.group(1), m.group(2)
                if slot == "B":
                    # strogaya: vse znacheniya klyuchey maskiruem
                    lines_out.append(f"{k}=<REDACTED>\n")
                else:
                    # umerennaya: tolko ochevidnye sekrety
                    if any(s in k for s in ("KEY","TOKEN","SECRET","PASSWORD","PASS","PRIVATE","SIGNING")):
                        lines_out.append(f"{k}=<REDACTED>\n")
                    else:
                        lines_out.append(f"{k}={v}\n")
    else:
        lines_out.append("# .env.public (sozdan avtomaticheski)\n")
    with open(dst_public,"w",encoding="utf-8") as f:
        f.writelines(lines_out)

def _pack_zip(root: str, out_zip: str):
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for base, _, files in os.walk(root):
            for fn in files:
                fp = os.path.join(base, fn)
                arc = os.path.relpath(fp, root).replace("\\","/")
                zf.write(fp, arc)

def _build(slot: str, dry_run: bool) -> Dict[str, Any]:
    mf = _load_manifest()
    inc = mf.get("include",[])
    exc = mf.get("exclude",[])
    files = _gather(inc, exc)
    ts = int(time.time())
    workdir = os.path.join(EXPORT_DIR, f"public_{ts}")
    os.makedirs(workdir, exist_ok=True)

    for p in files:
        _write_file(workdir, p)

    if mf.get("redact_env", True):
        _make_env_public(workdir, slot)

    if dry_run:
        return {"ok": True, "workdir": workdir, "zip": None, "slot": slot, "count": len(files)}

    zip_name = os.path.join(EXPORT_DIR, f"public_{ts}.zip")
    _pack_zip(workdir, zip_name)
    return {"ok": True, "workdir": workdir, "zip": zip_name, "slot": slot, "count": len(files)}

def build_public(dry_run: bool = True) -> Dict[str, Any]:
    os.makedirs(EXPORT_DIR, exist_ok=True)
    # B-slot, esli vklyuchili stroguyu sanitiatsiyu
    strict = (os.getenv("SANITIZE_STRICT","0") == "1")
    try:
        if strict:
            resB = _build("B", dry_run)
            if resB.get("ok"): 
                return resB
            # esli vdrug "ok" = False — probuem A
        resA = _build("A", dry_run)
        return resA
    except Exception as e:
        # katbek na A
        try:
            return _build("A", dry_run)
        except Exception as e2:
            return {"ok": False, "error": f"{e} / fallback: {e2}"}
# c=a+b