# -*- coding: utf-8 -*-
"""
Alias-paket: ester.* → suschestvuyuschie kornevye pakety.
Glavnaya tsel zdes — chtoby importy vida `ester.routes.xxx` shli v `routes.xxx`
bez pravok starogo koda.
"""
from __future__ import annotations
import importlib, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Probros paketa routes
_routes = importlib.import_module('routes')
# Zaregistriruem ego kak ester.routes, chtoby Python schital ego «podpaketom» ester
sys.modules.setdefault('ester.routes', _routes)

# Optsionalno mozhno probrasyvat i drugie pakety, esli oni vstrechayutsya v starykh importakh:
# _providers = importlib.import_module('providers')
# sys.modules.setdefault('ester.providers', _providers)