# -*- coding: utf-8 -*-
"""
modules/self/dynamic_loader.py — avtozagruzka rasshireniy iz SELF_CODE_ROOT/enabled s bezopasnoy registratsiey.

API:
  • load_all(app) -> dict {"loaded":[...], "errors":[...]}

Mosty:
- Yavnyy: (Inzheneriya ↔ Volya) novaya sposobnost podkhvatyvaetsya bez pravok app.py.
- Skrytyy #1: (Infoteoriya ↔ Audit) log zagruzok ponyaten i vozvraschaetsya naruzhu.
- Skrytyy #2: (Kibernetika ↔ Kontrol) neudachnye moduli ne lomayut server (best-effort).

Zemnoy abzats:
Eto «rozetka rasshireniy»: polozhil modul — sistema akkuratno ego vklyuchit.

# c=a+b
"""
from __future__ import annotations

import importlib.util, os, traceback
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def load_all(app) -> Dict[str, Any]:
    root = os.getenv("SELF_CODE_ROOT", "extensions")
    enabled = os.path.join(root, "enabled")
    loaded, errors = [], []
    try:
        os.makedirs(enabled, exist_ok=True)
        for fn in sorted(os.listdir(enabled)):
            if not fn.endswith(".py"): 
                continue
            path = os.path.join(enabled, fn)
            name = f"ext_{os.path.splitext(fn)[0]}"
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                mod = importlib.util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)
                if hasattr(mod, "register"):
                    mod.register(app)
                loaded.append(fn)
            except Exception as e:
                errors.append({"file": fn, "error": f"{e}", "trace": traceback.format_exc(limit=2)})
    except Exception as e:
        errors.append({"error": str(e)})
    return {"loaded": loaded, "errors": errors}