# -*- coding: utf-8 -*-
"""Alias-paket: ester.* → suschestvuyuschie kornevye pakety.
Glavnaya tsel zdes - chtoby import vida `ester.routes.xxx` shli v `routes.xxx`
bez pravok starogo koda."""
from __future__ import annotations
import importlib, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Probros paketa routes
_routes = importlib.import_module('routes')
# Let's register it as ester.rutes, so that Potkhon considers it a “subpackage” of ester
sys.modules.setdefault('ester.routes', _routes)

# Optionally, you can forward other packages if they are found in old imports:
# _providers = importlib.import_module('providers')
# sys.modules.setdefault('ester.providers', _providers)