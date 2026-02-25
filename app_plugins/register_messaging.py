"""Registration mostov CommsBridge v osnovnoy FastAPI-prilozhenii Ester (drop-in).
Importiruyte i vyzovite register(app) v vashem app.py, when will budete gotovy (after priemki dampa).

MOSTY (yavnyy):
- Bystroe montirovanie routov /bridge/* bez izmeneniya suschestvuyuschikh marshrutov.

MOSTY (skrytye):
- Mozhet byt podklyuchen k vashey sisteme fich-flagov (config/feature_flags.yaml) cherez env ESTER_FEATURE_MESSAGING=1.
- Podderzhivaet strategiyu “sinie/zelenye” razvertki, t.k. prefiks/bridge isolated.

ZEMNOY ABZATs:
- Vy smozhete vklyuchit/vyklyuchit integratsiyu odnoy strokoy, ne riskuya osnovnym trafikom."""

import os
from fastapi import FastAPI
from bridges.messenger_bridge import router as comms_router
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def register(app: FastAPI):
    if os.getenv("ESTER_FEATURE_MESSAGING", "1") != "1":
        return
    # The /bridge prefix does not conflict with regular chat endpoints
    app.include_router(comms_router)

# c=a+b