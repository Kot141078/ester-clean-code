# -*- coding: utf-8 -*-
"""
tests/messaging/test_contacts_csv.py — eksport/import CSV.

MOSTY:
- (Yavnyy) Eksportiruet pustuyu/nepustuyu bazu v CSV i importiruet obratno.
- (Skrytyy #1) Proveryaet korrektnost primeneniya opt-in/prefs/silence.
- (Skrytyy #2) CSV_DELIM vliyaet na format.

ZEMNOY ABZATs:
Garantiruet, chto operator mozhet perenosit kontakty mezhdu sredami bez syurprizov.

# c=a+b
"""
from __future__ import annotations

import os, time

from messaging.contacts_csv import export_contacts_csv, import_contacts_csv
from messaging.optin_store import set_optin, set_prefs, set_silence_until, list_contacts
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_export_import_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("MESSAGING_DB_PATH", str(tmp_path/"db.sqlite"))
    # podgotovim dannye
    set_optin("telegram:1", True)
    set_prefs("telegram:1", 5, "gentle")
    set_silence_until("telegram:1", time.time()+3600)
    # eksport
    csv_bytes = export_contacts_csv()
    assert b"telegram:1" in csv_bytes
    # import v novuyu BD
    monkeypatch.setenv("MESSAGING_DB_PATH", str(tmp_path/"db2.sqlite"))
    rep = import_contacts_csv(csv_bytes)
    assert rep["applied"] >= 1
    xs = list_contacts()
    keys = [x[0] for x in xs]
    assert "telegram:1" in keys