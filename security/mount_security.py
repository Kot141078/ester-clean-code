# -*- coding: utf-8 -*-
"""
security/mount_security.py — edinyy montirovschik RBAC middleware po ENV.

MOSTY:
- (Yavnyy) mount_security(app) — podklyuchaet RBACMiddleware, chitaya SECURITY_MODE.
- (Skrytyy #1) Ne menyaet marshruty; okhvatyvaet ikh po prefiksam.
- (Skrytyy #2) Druzhestvenen k air-gap: nikakoy vneshney kriptozavisimosti.

ZEMNOY ABZATs:
Odin vyzov — i adminka/eksporty pod zaschitoy: rol, parol/token i limit zaprosov. V lyuboy moment mozhno vyklyuchit.

# c=a+b
"""
from __future__ import annotations

import os
from fastapi import FastAPI
from .rbac_middleware import RBACMiddleware
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def mount_security(app: FastAPI) -> None:
    mode = (os.getenv("SECURITY_MODE","off") or "off").lower()
    # Podklyuchaem middleware odin raz
    app.add_middleware(RBACMiddleware, mode=mode)