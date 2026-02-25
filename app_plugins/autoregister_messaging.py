# -*- coding: utf-8 -*-
"""app_plugins/autoregister_messaging.py - plagin avtoregistratsii vsego messaging-steka.

MOSTY:
- (Yavnyy) register(app): podklyuchaet /messaging/register_all_plus i srazu dergaet ego registrator.
- (Skrytyy #1) Podderzhka avtozapuska po ENV (ESTER_AUTOREGISTER_MESSAGING=1) cherez before_first_request.
- (Skrytyy #2) “Sinie/zelenye”: povtornye vyzovy bezopasny, dubley marshrutov ne sozdayut.

ZEMNOY ABZATs:
V app.py dostatochno dobavit odnu stroku (ili prosto vystavit ENV) - i TG/WA/Proactive/Health/Metrics budut vklyucheny
bez izmeneniya suschestvuyuschey initsializatsii. Kontrakty ne menyayutsya, vse drop-in.

# c=a+b"""
from __future__ import annotations
import os
from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _do_register_all_plus(app: Flask) -> None:
    from routes.messaging_register_all_plus import register as reg_plus
    # We connect the recorder itself and then pull its endpoint locally
    reg_plus(app)
    try:
        with app.test_request_context():
            # We import in context so that the endpoints are already there
            pass
    except Exception:
        pass

def register(app: Flask, auto: bool | None = None) -> None:
    """Vklyuchit ves messaging-stek. Safely vyzyvat mnogokratno.
    Esli auto=True or ESTER_AUTOREGISTER_MESSAGING=1 — register khuk, kotoryy vypolnit podklyuchenie na pervom zaprose."""
    flag = os.getenv("ESTER_AUTOREGISTER_MESSAGING", "0") == "1" if auto is None else bool(auto)
    _do_register_all_plus(app)
    if flag:
        @app.before_first_request
        def _auto_enable():
            # Povtornyy vyzov bezopasen
            _do_register_all_plus(app)