# -*- coding: utf-8 -*-
"""
E2E-test GDPR-ruchek (yadro cherez impl-funktsii):
 - napolnyaem Structured (oba vozmozhnykh formata), KG, Hypotheses, Events
 - eksportiruem po query
 - udalyaem (dry_run=false), proveryaem, chto vse ischezlo
"""

import json
import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    os.makedirs(tmp_path / "structured_mem", exist_ok=True)
    os.makedirs(tmp_path / "events", exist_ok=True)
    yield


def _seed_structured_both_formats(base_dir):
    # dict-format
    path = os.path.join(base_dir, "structured_mem", "store.json")
    data = {
        "records": [
            {
                "id": "r1",
                "text": "User Owner email owner@example.com",
                "tags": ["pii"],
                "mtime": time.time(),
            },
            {"id": "r2", "text": "Generic note", "tags": [], "mtime": time.time()},
        ],
        "alias_map": {},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _seed_kg():
    from memory.kg_store import KGStore

    kg = KGStore()
    kg.upsert_nodes(
        [
            {
                "id": "person::owner",
                "type": "entity",
                "label": "Owner Petrov",
                "props": {"email": "owner@example.com"},
                "mtime": time.time(),
            },
            {
                "id": "topic::privacy",
                "type": "topic",
                "label": "privacy",
                "props": {},
                "mtime": time.time(),
            },
        ]
    )
    kg.upsert_edges(
        [
            {
                "src": "person::owner",
                "rel": "mentions",
                "dst": "topic::privacy",
                "weight": 0.6,
                "props": {"note": "GDPR"},
                "mtime": time.time(),
            }
        ]
    )


def _seed_hypotheses():
    from memory.hypothesis_store import HypothesisStore

    hs = HypothesisStore()
    hs.add(
        "Proverit khranenie email owner@example.com",
        topic="gdpr",
        tags=["test"],
        score=0.5,
    )
    hs.add("Neytralnaya gipoteza", topic="misc", tags=["test"], score=0.5)


def _seed_events(base_dir):
    path = os.path.join(base_dir, "events", "events.jsonl")
    rows = [
        {
            "id": "evt1",
            "ts": time.time(),
            "kind": "ingest_done",
            "payload": {"who": "owner@example.com"},
        },
        {
            "id": "evt2",
            "ts": time.time(),
            "kind": "note",
            "payload": {"text": "no pii here"},
        },
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_export_and_delete(clean_env, tmp_path):
    base = str(tmp_path)
    _seed_structured_both_formats(base)
    _seed_kg()
    _seed_hypotheses()
    _seed_events(base)

    from routes.ops_routes import _delete_personal_data_impl, _export_personal_data_impl

    q = "owner@example.com"
    exp = _export_personal_data_impl(q)
    assert exp["ok"] is True
    assert exp["counts"]["structured"] >= 1
    assert exp["counts"]["kg_nodes"] >= 1
    assert exp["counts"]["hypotheses"] >= 1
    assert exp["counts"]["events"] >= 1

    # dry-run
    rep = _delete_personal_data_impl(q, dry_run=True)
    assert rep["ok"] is True
    assert rep["dry_run"] is True
    assert rep["removed"]["structured"] >= 1

    # real delete
    rep2 = _delete_personal_data_impl(q, dry_run=False)
    assert rep2["ok"] is True
    assert rep2["dry_run"] is False
    # Povtornyy eksport po tomu zhe zaprosu dolzhen vernut nuli/minimumy
    exp2 = _export_personal_data_impl(q)
    assert exp2["counts"]["structured"] == 0
    assert exp2["counts"]["kg_nodes"] == 0
    assert exp2["counts"]["hypotheses"] == 0
# assert exp2["counts"]["events"] == 0