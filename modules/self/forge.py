# modules/self/forge.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import io
import re
import json
import time
import shutil
import hashlib
from typing import Iterable, List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ALLOW_DIRS = [
    "modules",
    "routes",
    "templates",
    "static",
    "configs",
    "security",
]
BKP = os.getenv("ESTER_BKP", "data/backups/forge")
os.makedirs(BKP, exist_ok=True)

def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _is_allowed_path(p: str) -> bool:
    p = p.replace("\\", "/")
    if ".." in p:
        return False
    return any(p.startswith(d + "/") or p == d for d in ALLOW_DIRS)

def _norm_text(s: str) -> str:
    # normalizatsiya kontsov strok
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s

def dry_run_apply(target_path: str, new_text: str) -> Dict[str, Any]:
    """
    Proverka izmeneniy bez zapisi.
    """
    target_path = target_path.replace("\\", "/")
    if not _is_allowed_path(target_path):
        return {"ok": False, "error": "path_not_allowed", "path": target_path}

    try:
        old = ""
        if os.path.exists(target_path):
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                old = f.read()
        old_n = _norm_text(old)
        new_n = _norm_text(new_text)
        return {
            "ok": True,
            "path": target_path,
            "old_sha": _sha256(old_n.encode("utf-8")),
            "new_sha": _sha256(new_n.encode("utf-8")),
            "diff_hint": len(old_n) != len(new_n),
        }
    except Exception as e:
        return {"ok": False, "error": f"{e}"}

def apply_changes(changes: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Primenyaet spisok {path, text}. Delaet bekap staroy versii v BKP.
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    report = {"ok": True, "applied": [], "skipped": [], "errors": []}

    for ch in changes:
        p = ch.get("path", "").strip().replace("\\", "/")
        text = _norm_text(ch.get("text", ""))

        if not p or not _is_allowed_path(p):
            report["skipped"].append({"path": p, "reason": "path_not_allowed"})
            continue

        try:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            # Bekap
            if os.path.isfile(p):
                old = open(p, "r", encoding="utf-8", errors="ignore").read()
                safe = p.replace('/', '_').replace('\\', '_')
                bkp = os.path.join(BKP, f"{safe}.{ts}.bak")
                try:
                    open(bkp, "w", encoding="utf-8").write(old)
                except Exception:
                    pass
            # Zapis
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            report["applied"].append({"path": p})
        except Exception as e:
            report["errors"].append({"path": p, "error": f"{e}"})
            report["ok"] = False

    return report

def list_backups(limit: int = 100) -> List[str]:
    try:
        items = sorted(os.listdir(BKP), reverse=True)
        return items[:limit]
    except Exception:
        return []

def restore_backup(filename: str, dest_path: str) -> Dict[str, Any]:
    """
    Vosstanovlenie iz bekapa.
    """
    try:
        src = os.path.join(BKP, filename)
        if not os.path.isfile(src):
            return {"ok": False, "error": "backup_not_found"}
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        shutil.copy2(src, dest_path)
        return {"ok": True, "restored": dest_path}
    except Exception as e:
        return {"ok": False, "error": f"{e}"}

def allow_dirs() -> List[str]:
    return list(ALLOW_DIRS)

def add_allow_dir(d: str) -> None:
    d = d.strip().strip("/").strip("\\")
    if d and d not in ALLOW_DIRS:
        ALLOW_DIRS.append(d)

# CLI-khelpery
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="Tolko dry-run")
    ap.add_argument("--apply", action="store_true", help="Primenit izmeneniya")
    ap.add_argument("--stdin", action="store_true", help="Chitat JSON iz stdin {changes:[{path,text},...]}")
    ap.add_argument("--list", action="store_true", help="Spisok bekapov")
    ap.add_argument("--restore", type=str, help="Imya fayla bekapa")
    ap.add_argument("--dest", type=str, help="Kuda vosstanovit")
    args = ap.parse_args()

    if args.list:
        for it in list_backups():
            print(it)
        raise SystemExit(0)

    if args.restore:
        if not args.dest:
            print("Nuzhen --dest")
            raise SystemExit(2)
        r = restore_backup(args.restore, args.dest)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        raise SystemExit(0)

    if args.stdin:
        data = json.load(io.TextIOWrapper(buffer=os.fdopen(0, "rb"), encoding="utf-8"))
        changes = data.get("changes") or []
        if args.dry:
            out = [dry_run_apply(c.get("path",""), c.get("text","")) for c in changes]
            print(json.dumps(out, ensure_ascii=False, indent=2))
        elif args.apply:
            r = apply_changes(changes)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print("Ukazhi --dry ili --apply")
    else:
        print("Nichego ne sdelano. Ispolzuy --stdin.")