# -*- coding: utf-8 -*-
# Automatically adding the repository root to sys.path + alias ESTER -> ESTER.
import sys, importlib, pathlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = pathlib.Path(__file__).resolve().parent
r = str(ROOT)
if r not in sys.path:
    sys.path.insert(0, r)

# If the uppercase ESTER is there, but the ESTER is not imported, we make an alias.
if 'ester' not in sys.modules:
    try:
        m = importlib.import_module('ESTER')
        sys.modules['ester'] = m
    except Exception:
        pass