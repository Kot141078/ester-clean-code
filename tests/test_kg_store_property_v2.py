# -*- coding: utf-8 -*-
"""
Property-testy dlya memory/kg_store.py (v2):
 - LWW po mtime dlya uzlov, merge props, zaschita ot "starykh" apdeytov
 - Unikalnost rebra po (src, rel, dst), weight=max, props LWW
 - neighbors/query/export/import — konsistentnost i idempotentnost
"""

import copy
import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_nodes_lww_and_props_merge(clean_env):
    from memory.kg_store import KGStore

    kg = KGStore()

    # 1) Sozdaem uzel s rannim mtime
    node_id = "topic::replication"
    t0 = 1_000.0
    out = kg.upsert_nodes(
        [
            {
                "id": node_id,
                "type": "topic",
                "label": "Replication",
                "props": {"a": 1, "b": 2},
                "mtime": t0,
            }
        ]
    )
    assert out == [node_id]

    # 2) Obnovlyaem uzel bolee novym mtime: collision po 'b', novyy klyuch 'c'
    t1 = 2_000.0
    out = kg.upsert_nodes(
        [
            {
                "id": node_id,
                "type": "topic",
                "label": "Replication CRDT",
                "props": {"b": 3, "c": 9},
                "mtime": t1,
            }
        ]
    )
    assert out == [node_id]

    nd = kg.query_nodes(q="replication", type="topic", limit=10)[0]
    assert nd["label"] == "Replication CRDT"
    # props: 'b' vzyat iz novoy versii, 'a' sokhranen, 'c' dobavlen
    assert nd["props"] == {"a": 1, "b": 3, "c": 9}
    assert nd["mtime"] == pytest.approx(t1)

    # 3) Pytaemsya "starym" apdeytom dobavit novyy klyuch — ne dolzhno proyti
    t_old = 500.0
    kg.upsert_nodes(
        [
            {
                "id": node_id,
                "type": "topic",
                "label": "Should be ignored (old)",
                "props": {"d": 100},
                "mtime": t_old,
            }
        ]
    )
    nd2 = kg.query_nodes(q="replication", type="topic", limit=10)[0]
    # label i props ne izmenilis
    assert nd2["label"] == "Replication CRDT"
    assert nd2["props"] == {"a": 1, "b": 3, "c": 9}
    assert nd2["mtime"] == pytest.approx(t1)


def test_edges_uniqueness_weight_max_props_lww(clean_env):
    from memory.kg_store import KGStore

    kg = KGStore()
    # Podgotovim uzly
    kg.upsert_nodes(
        [
            {"id": "a", "type": "topic", "label": "A", "props": {}, "mtime": 1000.0},
            {"id": "b", "type": "artifact", "label": "B", "props": {}, "mtime": 1000.0},
        ]
    )

    # 1) Sozdaem rebro (a -supports-> b) s vesom 0.4 i props={'p':1}
    e1 = kg.upsert_edges(
        [
            {
                "src": "a",
                "rel": "supports",
                "dst": "b",
                "weight": 0.4,
                "props": {"p": 1},
                "mtime": 1000.0,
            }
        ]
    )
    assert len(e1) == 1
    eid = e1[0]
    ed = kg.query_edges(rel="supports", src="a", dst="b", limit=10)[0]
    assert ed["id"] == eid
    assert ed["weight"] == pytest.approx(0.4)
    assert ed["props"] == {"p": 1}
    assert ed["mtime"] == pytest.approx(1000.0)

    # 2) Obnovlyaem tem zhe klyuchom rebra, no s bOlshim vesom i BOLEE STARYM mtime
    e2 = kg.upsert_edges(
        [
            {
                "src": "a",
                "rel": "supports",
                "dst": "b",
                "weight": 0.7,
                "props": {"p": 2, "q": 9},
                "mtime": 900.0,
            }
        ]
    )
    assert e2 == [eid]
    ed2 = kg.query_edges(rel="supports", src="a", dst="b", limit=10)[0]
    # weight=max(old,new) — obnovilsya
    assert ed2["weight"] == pytest.approx(0.7)
    # props pri starom mtime ne perezapisalis
    assert ed2["props"] == {"p": 1}
    # mtime ostalsya prezhnim
    assert ed2["mtime"] == pytest.approx(1000.0)

    # 3) Teper svezhiy apdeyt s props i mtime novee
    e3 = kg.upsert_edges(
        [
            {
                "src": "a",
                "rel": "supports",
                "dst": "b",
                "weight": 0.6,
                "props": {"p": 5, "r": 1},
                "mtime": 2000.0,
            }
        ]
    )
    assert e3 == [eid]
    ed3 = kg.query_edges(rel="supports", src="a", dst="b", limit=10)[0]
    # weight ostalsya maksimalnym (0.7)
    assert ed3["weight"] == pytest.approx(0.7)
    # props obnovleny po LWW i merged
    assert ed3["props"] == {"p": 5, "r": 1}
    assert ed3["mtime"] == pytest.approx(2000.0)


def test_neighbors_and_query_limits(clean_env):
    from memory.kg_store import KGStore

    kg = KGStore()
    kg.upsert_nodes(
        [
            {"id": "x", "type": "topic", "label": "X", "props": {}, "mtime": 1_000.0},
            {"id": "y", "type": "topic", "label": "Y", "props": {}, "mtime": 1_000.0},
            {"id": "z", "type": "topic", "label": "Z", "props": {}, "mtime": 1_000.0},
        ]
    )
    kg.upsert_edges(
        [
            {
                "src": "x",
                "rel": "mentions",
                "dst": "y",
                "weight": 0.1,
                "props": {},
                "mtime": 1_100.0,
            },
            {
                "src": "z",
                "rel": "mentions",
                "dst": "x",
                "weight": 0.2,
                "props": {},
                "mtime": 1_200.0,
            },
        ]
    )

    nb = kg.neighbors("x")
    assert nb["node"]["id"] == "x"
    # out: x->y, in: z->x
    out_ids = {e["dst"] for e in nb["out"]}
    in_ids = {e["src"] for e in nb["in"]}
    assert out_ids == {"y"}
    assert in_ids == {"z"}

    # query_nodes s filtrom po tipu i limitom
    qnodes = kg.query_nodes(q="", type="topic", limit=2)
    assert len(qnodes) == 2

    # query_edges po rel
    qedges = kg.query_edges(rel="mentions", limit=10)
    assert len(qedges) == 2


def test_export_import_idempotency(clean_env):
    from memory.kg_store import KGStore

    kg = KGStore()
    kg.upsert_nodes(
        [
            {
                "id": "n1",
                "type": "topic",
                "label": "N1",
                "props": {"k": 1},
                "mtime": 1000.0,
            },
            {
                "id": "n2",
                "type": "topic",
                "label": "N2",
                "props": {"k": 2},
                "mtime": 1000.0,
            },
        ]
    )
    kg.upsert_edges(
        [
            {
                "src": "n1",
                "rel": "supports",
                "dst": "n2",
                "weight": 0.5,
                "props": {"p": 1},
                "mtime": 1200.0,
            }
        ]
    )

    payload = kg.export_all()
    assert "nodes" in payload and "edges" in payload
    n0, e0 = len(payload["nodes"]), len(payload["edges"])
    assert n0 >= 2 and e0 >= 1

    # Novyy stor, import togo zhe — idempotentnyy merdzh
    kg2 = KGStore()
    res = kg2.import_all(payload)
    assert res["nodes"] >= 2
    assert res["edges"] >= 1
    payload2 = kg2.export_all()
    assert len(payload2["nodes"]) == n0
# assert len(payload2["edges"]) == e0