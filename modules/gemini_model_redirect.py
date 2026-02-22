# modules/gemini_model_redirect.py
#
# Globalnyy patch dlya zaprosov k Gemini:
# esli gde-to v kode zashit staryy put c "gemini-1.5-pro",
# my perepisyvaem URL na model iz peremennoy okruzheniya GEMINI_MODEL.
#
# Eto tonkiy adapter nad requests, ne trogayuschiy ostalnoy kod Ester.

import os
import logging

import requests
from requests.sessions import Session
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

# Khost Gemini API
_TARGET_HOST = "generativelanguage.googleapis.com"
# Staroe, «zashitoe» imya modeli, kotoroe daet 404 v tvoem proekte
_OLD_MODEL = "gemini-1.5-pro"
# Novaya model — berem iz okruzheniya, po umolchaniyu gemini-2.5-flash
_NEW_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _install_patch() -> None:
    """
    Odin raz perekhvatyvaem Session.request i perepisyvaem URL,
    esli on ukazyvaet na staruyu model Gemini.
    """
    # Chtoby ne patchit neskolko raz pri povtornom importe
    if getattr(Session, "_ester_gemini_patched", False):
        log.info("[gemini_redirect] already patched, skipping")
        return

    original_request = Session.request

    def patched_request(self, method, url, *args, **kwargs):
        # «Most 1» (yavnyy): svyaz mezhdu sloem setevykh vyzovov
        # i urovnem modeley LLM — zdes my kak raz shem ikh vmeste.
        if _TARGET_HOST in url and _OLD_MODEL in url:
            new_url = url.replace(_OLD_MODEL, _NEW_MODEL)
            if new_url != url:
                log.info(
                    "[gemini_redirect] rewrite model %s -> %s",
                    _OLD_MODEL,
                    _NEW_MODEL,
                )
                url = new_url
        return original_request(self, method, url, *args, **kwargs)

    Session._ester_gemini_patched = True
    Session.request = patched_request

    log.info(
        "[gemini_redirect] installed; host=%s, old_model=%s, new_model=%s",
        _TARGET_HOST,
        _OLD_MODEL,
        _NEW_MODEL,
    )


# Ustanavlivaem patch pri importe modulya
try:
    _install_patch()
except Exception as e:  # na vsyakiy sluchay ne valim ves protsess
    log.exception("[gemini_redirect] failed to install patch: %s", e)