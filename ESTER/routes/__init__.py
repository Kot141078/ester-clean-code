# -*- coding: utf-8 -*-
"""
Tonkiy proksi: sam paket ester.routes zamenyaetsya na realnyy routes.
Eto pozvolyaet, naprimer, import ester.routes.rag_routes → routes.rag_routes.
"""
from importlib import import_module as _im
import sys as _sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_real = _im('routes')
_sys.modules[__name__] = _real