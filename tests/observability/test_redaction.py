# -*- coding: utf-8 -*-
"""
tests/observability/test_redaction.py — proverki maskirovki PII i log-filtra.

MOSTY:
- (Yavnyy) Maskiruem email/telefon/IP/UUID/kartu/token; rekursivnaya redaktsiya dict/list.
- (Skrytyy #1) Podklyuchaem RedactFilter k loggeru i ubezhdaemsya, chto soobschenie redaktiruetsya.
- (Skrytyy #2) Khvostovye simvoly sokhranyayutsya dlya sopostavleniya.

ZEMNOY ABZATs:
# Esli test zelenyy — vklyuchennaya redaktsiya ne lomaet logi, a privatnye dannye v nikh ne utekut. c=a+b
"""
from __future__ import annotations

import logging

from observability.redaction import redact_text, redact_dict, attach_redaction_to_logger
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_redact_text_basic():
    t = "Pochta: john.doe+dev@acme.io, Tel:+1-202-555-0199, IP: 192.168.1.77, UUID=123e4567-e89b-12d3-a456-426614174000, Card: 4111 1111 1111 1111"
    r = redact_text(t)
    assert "acme.io" in r
    assert "john" not in r  # lokalnaya chast skryta
    assert "202-555" not in r  # telefon skryt
    assert "x.x.x.77" in r  # IP redaktirovan
    assert "426614174000"[-4:] in r  # khvost viden
    assert "4111" not in r  # karta skryta

def test_redact_dict_recursive_and_logger():
    d = {"email":"alice@example.com","phones":["+380 67 123 45 67"],"nested":{"ip":"10.0.0.1","token":"A"*48}}
    rd = redact_dict(d)
    s = str(rd)
    assert "example.com" in s and "alice" not in s
    assert "A" * 10 not in s  # token skryt

    logger = logging.getLogger("redact-test")
    attach_redaction_to_logger(logger)
    rec = logging.LogRecord("redact-test", logging.INFO, __file__, 1, "mail %s", ("bob@corp.org",), None)
    assert logger.filters[0].filter(rec)
    assert "bob@" not in rec.msg and "corp.org" in rec.msg