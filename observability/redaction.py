# -*- coding: utf-8 -*-
"""
observability/redaction.py — redaktsiya PII i «nizkiy profil» logov.

MOSTY:
- (Yavnyy) redact_text/redact_dict + RedactFilter dlya loggera: skryvaem email/telefony/IP/UUID/karty/tokeny.
- (Skrytyy #1) Myagkie khvosty: ostavlyaem poslednie N simvolov u markerov — chtoby umet sopostavlyat keysy bez utechki.
- (Skrytyy #2) Dekorator @redact_outputs dlya obertki funktsiy/khendlerov (safety-by-default bez lomki kontraktov).

ZEMNOY ABZATs:
Pishem v logi to, chto pomogaet obsluzhivat sistemu, no ne vydaet privatnye dannye polzovateley i kontaktov.
# Podklyuchenie — odnoy strokoy: attach_redaction_to_logger(logger). c=a+b
"""
from __future__ import annotations

import json
import logging
import os
import re
from copy import deepcopy
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_KEEP_TAIL = max(0, int(os.getenv("REDACT_KEEP_LAST_N", "4")))
_ENABLE = os.getenv("REDACT_ENABLE", "1") == "1"

# Bazovye patterny PII
_PAT_EMAIL = re.compile(r"([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]{0,32})@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_PAT_PHONE = re.compile(r"(?<!\d)(\+?\d{1,3}[- ]?)?(\d{3})[- ]?(\d{2,3})[- ]?(\d{2})[- ]?(\d{2})(?!\d)")
_PAT_IPV4  = re.compile(r"\b(\d{1,3}\.){3}\d{1,3}\b")
_PAT_UUID  = re.compile(r"\b[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}\b")
_PAT_TOKEN = re.compile(r"\b[A-Za-z0-9-_]{24,}\b")
_PAT_CARD  = re.compile(r"\b(\d[ -]*?){13,19}\b")

def _tail_mask(s: str, prefix_mask: str = "●") -> str:
    if not s:
        return s
    if _KEEP_TAIL <= 0:
        return prefix_mask * len(s)
    # Keep at most len(s)-1 chars visible to ensure at least one masked symbol.
    tail_len = min(_KEEP_TAIL, max(0, len(s) - 1))
    tail = s[-tail_len:] if tail_len else ""
    return (prefix_mask * max(0, len(s) - len(tail))) + tail

def redact_text(text: str) -> str:
    """Redaktiruet stroku, maskiruya PII."""
    if not _ENABLE or not isinstance(text, str) or not text:
        return text

    def _repl_email(m: re.Match) -> str:
        head_first = m.group(1)
        head_rest  = m.group(2)
        dom = m.group(3)
        return _tail_mask(head_first + head_rest) + "@" + dom

    t = text
    t = _PAT_EMAIL.sub(_repl_email, t)
    t = _PAT_PHONE.sub(lambda m: _tail_mask(re.sub(r"[^\d]", "", m.group(0))), t)
    t = _PAT_IPV4.sub(lambda m: "x.x.x." + m.group(0).split(".")[-1], t)
    t = _PAT_UUID.sub(lambda m: _tail_mask(m.group(0)), t)
    t = _PAT_TOKEN.sub(lambda m: _tail_mask(m.group(0)), t)
    t = _PAT_CARD.sub(lambda m: _tail_mask(re.sub(r"[^\d]", "", m.group(0))), t)
    return t

def redact_dict(obj: Any) -> Any:
    """Rekursivnaya redaktsiya vsekh strokovykh znacheniy v strukturakh."""
    if isinstance(obj, dict):
        return {k: redact_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_dict(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj

class RedactFilter(logging.Filter):
    """Filtr dlya loggera: primenyaet redact_text k message i polyam record.__dict__."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            # Perepakuem message (ostavlyaya formatirovanie logging)
            record.msg = redact_text(msg)
            # Poprobuem redaktirovat extras, esli tam dict/json
            for k, v in list(record.__dict__.items()):
                if isinstance(v, str):
                    record.__dict__[k] = redact_text(v)
                elif isinstance(v, (dict, list)):
                    record.__dict__[k] = redact_dict(v)
        except Exception:
            pass
        return True

def attach_redaction_to_logger(logger: logging.Logger) -> None:
    """Podklyuchit RedactFilter k lyubomu loggeru odin raz."""
    for f in logger.filters:
        if isinstance(f, RedactFilter):
            return
    logger.addFilter(RedactFilter())

def redact_outputs(fn):
    """Dekorator: primenyaet redact_dict k rezultatu funktsii (esli eto dict/list/str)."""
    def _wrap(*args, **kwargs):
        res = fn(*args, **kwargs)
        return redact_dict(res)
    _wrap.__name__ = fn.__name__
    _wrap.__doc__ = fn.__doc__
    return _wrap
