# -*- coding: utf-8 -*-
# Avtodobavlenie kornya repozitoriya v sys.path + alias ESTER -> ester.
import sys, importlib, pathlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = pathlib.Path(__file__).resolve().parent
r = str(ROOT)
if r not in sys.path:
    sys.path.insert(0, r)

# Esli verkhniy registr ESTER est, a 'ester' ne importiruetsya — delaem alias.
if 'ester' not in sys.modules:
    try:
        m = importlib.import_module('ESTER')
        sys.modules['ester'] = m
    except Exception:
        pass