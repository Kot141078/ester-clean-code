from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
"""
Paket routes
Soderzhit Flask blueprints dlya moduley «Ester».
"""


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# zaglushka dlya init: poka net bp/router/register_*_routes
def register(app):
    return True

# === /AUTOSHIM ===