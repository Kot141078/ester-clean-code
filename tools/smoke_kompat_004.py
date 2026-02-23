# -*- coding: utf-8 -*-
"""
tools/smoke_kompat_004.py — proverka sitecustomize‑shvov bez syntax stubs, s lokalnym path‑bootstrap.
# c=a+b
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Lokalnyy bootstrap k kornyu proekta (../ ot tools/)
_root = str(Path(__file__).resolve().parents[1])
if _root not in sys.path:
    sys.path.insert(0, _root)

def trycall(expr: str) -> str | bool:
    try:
        ns = {}
        exec(expr, ns, ns)
        return True
    except Exception as e:
        return f"ERR:{e}"

out = {
  "env_no_stubs": trycall("import os; os.environ.get('ESTER_IMPORT_STUBS_AB')=='B'"),
  "jwt_optional": trycall("import flask_jwt_extended as fje; hasattr(fje,'verify_jwt_in_request_optional')"),
  "loop_status": trycall("from modules.thinking.loop_full import status; callable(status)"),
  "think_stop": trycall("import importlib; "
                        "ok=False\n"
                        "try:\n"
                        "  from modules.thinking.think_core import stop\n"
                        "  ok=callable(stop)\n"
                        "except Exception:\n"
                        "  m=importlib.import_module('thinking.think_core')\n"
                        "  ok=getattr(m,'stop', None) is not None\n"
                        "ok"),
}

print(json.dumps(out, ensure_ascii=False, indent=2))