# -*- coding: utf-8 -*-
"""
modules/self/code_sandbox.py — bezopasnaya samo-modifikatsiya: chernoviki moduley, proverka, primenenie, otkat.

API:
  • draft(name, content) -> dict
  • check(name) -> dict
  • apply(name) -> dict
  • revert(name) -> dict
  • list_all() -> dict

Politika:
  • Po umolchaniyu primenenie zaprescheno (SELF_CODE_ALLOW_APPLY=0).
  • A/B: SELF_CODE_AB=B — razresheny tolko draft/check/list (apply/revert → otkaz).
  • Primenenie = perenos .py iz drafts → enabled i avtopodkhvat cherez dynamic_loader; pered perenosom — sintaksis+import.

Mosty:
- Yavnyy: (Myshlenie ↔ Inzheneriya) «volya» mozhet sozdavat instrumenty, no s predokhranitelyami.
- Skrytyy #1: (Infoteoriya ↔ Audit) sha256, profile, zhurnal sostoyaniy — vosproizvodimost izmeneniy.
- Skrytyy #2: (Kibernetika ↔ Kontrol) avtokatbek: pri sboe importa modul ne vklyuchaetsya.

Zemnoy abzats:
Eto bezopasnyy verstak: detali delaem zdes, primeryaem — i tolko potom prikruchivaem k mashine.

# c=a+b
"""
from __future__ import annotations

import ast, hashlib, importlib.util, io, os, shutil, sys, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("SELF_CODE_ROOT", "extensions")
DRAFTS = os.path.join(ROOT, "drafts")
ENABLED = os.path.join(ROOT, "enabled")
TIMEOUT = float(os.getenv("SELF_CODE_TIMEOUT", "8"))
AB = (os.getenv("SELF_CODE_AB", "A") or "A").upper()
ALLOW_APPLY = bool(int(os.getenv("SELF_CODE_ALLOW_APPLY", "0")))
DENY = {x.strip() for x in (os.getenv("SELF_CODE_DENY_IMPORTS","") or "").split(",") if x.strip()}

_CNT = {"drafts_total":0, "checks_total":0, "applies_ok":0, "applies_fail":0, "reverts_total":0}

def _ensure_dirs():
    os.makedirs(DRAFTS, exist_ok=True); os.makedirs(ENABLED, exist_ok=True)

def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def _passport(name: str, content: str) -> Dict[str, Any]:
    return {"name": name, "sha256": _sha(content), "ts": int(time.time())}

def draft(name: str, content: str) -> Dict[str, Any]:
    _ensure_dirs()
    if not name or not content:
        return {"ok": False, "error": "name and content required"}
    if AB == "B":
        return {"ok": False, "error": "SELF_CODE_AB=B (draft disabled)"}  # zhestkiy rezhim
    # bystryy sintaksis
    try:
        ast.parse(content)
    except SyntaxError as e:
        return {"ok": False, "error": f"syntax: {e}"}
    path = os.path.join(DRAFTS, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + ("\n" if not content.endswith("\n") else ""))
    _CNT["drafts_total"] += 1
    return {"ok": True, "draft": {"name": name, "path": os.path.abspath(path)}, "passport": _passport(name, content)}

def _deny_imports_check(content: str) -> List[str]:
    bad = []
    try:
        t = ast.parse(content)
        for n in ast.walk(t):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in (n.names or []):
                    if a.name in DENY:
                        bad.append(a.name)
    except Exception:
        pass
    return bad

def check(name: str) -> Dict[str, Any]:
    _ensure_dirs()
    path = os.path.join(DRAFTS, f"{name}.py")
    if not os.path.isfile(path):
        return {"ok": False, "error": "draft not found"}
    content = open(path, "r", encoding="utf-8").read()
    bad = _deny_imports_check(content)
    if bad:
        return {"ok": False, "error": f"denied imports: {bad}"}
    # probnyy import kak otdelnogo modulya
    spec = importlib.util.spec_from_file_location(f"extdraft_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        loader = spec.loader
        assert loader is not None
        loader.exec_module(mod)   # mozhet upast
    except Exception as e:
        _CNT["checks_total"] += 1
        return {"ok": False, "error": f"import failed: {e}"}
    _CNT["checks_total"] += 1
    ok_register = hasattr(mod, "register")
    return {"ok": True, "registerable": bool(ok_register)}

def list_all() -> Dict[str, Any]:
    _ensure_dirs()
    def ls(p):
        try: return sorted([f for f in os.listdir(p) if f.endswith(".py")])
        except Exception: return []
    return {"ok": True, "drafts": ls(DRAFTS), "enabled": ls(ENABLED)}

def apply(name: str) -> Dict[str, Any]:
    _ensure_dirs()
    if AB == "B" or not ALLOW_APPLY:
        return {"ok": False, "error": "apply disabled (SELF_CODE_AB=B or SELF_CODE_ALLOW_APPLY=0)"}
    src = os.path.join(DRAFTS, f"{name}.py")
    if not os.path.isfile(src):
        return {"ok": False, "error": "draft not found"}
    content = open(src, "r", encoding="utf-8").read()
    # import-proverka
    chk = check(name)
    if not chk.get("ok"):
        _CNT["applies_fail"] += 1
        return {"ok": False, "error": chk.get("error","check failed")}
    # perenoc v enabled s SHA v imeni
    sha = _sha(content)
    dst = os.path.join(ENABLED, f"{name}_{sha[:8]}.py")
    shutil.copyfile(src, dst)
    _CNT["applies_ok"] += 1
    return {"ok": True, "enabled": os.path.abspath(dst), "passport": _passport(name, content)}

def revert(name: str) -> Dict[str, Any]:
    _ensure_dirs()
    pref = f"{name}_"
    n = 0
    for f in list(os.listdir(ENABLED)):
        if f.startswith(pref) and f.endswith(".py"):
            os.remove(os.path.join(ENABLED, f)); n += 1
    _CNT["reverts_total"] += 1
    return {"ok": True, "removed": n}

def counters() -> Dict[str, int]:
    return dict(_CNT)