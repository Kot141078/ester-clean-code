# -*- coding: utf-8 -*-
import json
import os
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def test_quote_once(client, tmp_path, monkeypatch):  # predpolagaem fiksturu Flask test client v proekte
    # Ispolzuem vremennyy docs-root, chtoby test ne zavisel ot prav na USERPROFILE.
    base = tmp_path / "docs"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ESTER_DOCS_DIR", str(base))
    p = base / "e2e_note.txt"
    needle = "E2E — eto skvoznaya proverka ot UI do BD."
    with open(p, "w", encoding="utf-8") as f:
        f.write(needle + "\n")

    # status
    rv = client.get("/ester/rag/docs/status")
    if rv.status_code == 404:
        pytest.skip("RAG docs routes are not mounted in this build")
    assert rv.status_code == 200
    payload = rv.get_json()
    assert payload["ok"] and payload["exists"]

    # quote_once
    rv = client.post("/ester/rag/docs/quote_once",
                     data=json.dumps({"pattern": needle, "wrap": 1}),
                     content_type="application/json")
    if rv.status_code == 404:
        pytest.skip("RAG quote route is not mounted in this build")
    assert rv.status_code == 200
    payload = rv.get_json()
    assert payload["ok"] and payload["found"]
    assert needle in payload["quote"]

    # chat-most
    msg = f"Naydi doslovnuyu stroku «{needle}». Otvet TOLKO etoy tsitatoy."
    rv = client.post("/ester/chat/quote",
                     data=json.dumps({"message": msg}),
                     content_type="application/json")
    if rv.status_code == 404:
        pytest.skip("Chat quote route is not mounted in this build")
    assert rv.status_code == 200
    payload = rv.get_json()
    assert payload["ok"]
    assert needle in payload["answer"]
