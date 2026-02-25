# modules/gemini_model_redirect.py
#
# Global patch for requests to Gemini:
# if somewhere in the code you sew up the old path to “gemini-1.5-pro”,
# my perepisyvaem URL na model iz peremennoy okruzheniya GEMINI_MODEL.
#
# This is a thin adapter over the controller that does not affect the rest of Esther's code.

import os
import logging

import requests
from requests.sessions import Session
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

# Khost Gemini API
_TARGET_HOST = "generativelanguage.googleapis.com"
# The old, "protect" model name that gives 404 in your project
_OLD_MODEL = "gemini-1.5-pro"
# New model - we take it from the environment, by default Gemini 2.5-flush
_NEW_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _install_patch() -> None:
    """We intercept Session.request once and rewrite the URL,
    if it points to the old Gemini model."""
    # To avoid patching several times when re-importing
    if getattr(Session, "_ester_gemini_patched", False):
        log.info("[gemini_redirect] already patched, skipping")
        return

    original_request = Session.request

    def patched_request(self, method, url, *args, **kwargs):
        # "Bridge 1" (explicit): communication between the network call layer
        # and the level of LLM models - here we are just diagramming them together.
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


# Install the patch when importing a module
try:
    _install_patch()
except Exception as e:  # just in case, don’t ruin the whole process
    log.exception("[gemini_redirect] failed to install patch: %s", e)