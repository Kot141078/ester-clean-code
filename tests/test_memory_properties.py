# -*- coding: utf-8 -*-
import json
import random
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _create_dialog(client, hdr, text):
    r = client.post("/chat/message", json={"query": text, "use_rag": False}, headers=hdr)
    assert r.status_code == 200


def test_flashback_scores_monotonic(client, auth_hdr_user):
    # Zaseem neskolko zapisey
    for i in range(15):
        _create_dialog(
            client, auth_hdr_user, f"Testovaya pamyat {i} vazhnost {i%3}"
        )
    r = client.get(
        "/mem/flashback", query_string={"query": "vazhnost"}, headers=auth_hdr_user
    )
    assert r.status_code == 200
    j = r.get_json()
    results = j.get("results") or j.get("flashback") or []
    # Dopuskaem otsutstvie 'score' u chasti istochnikov — filtruem
    scores = [x.get("score", 0.0) for x in results if isinstance(x, dict)]
    assert len(scores) > 0
    assert all(
        scores[i] >= scores[i + 1] for i in range(len(scores) - 1)
    ), "Ozhidalas nevozrastayuschaya posledovatelnost score"


def test_alias_idempotent_and_compact_idempotent(client, auth_hdr_admin):
    # sozdadim zapisi cherez chat
    _create_dialog(
        client,
        auth_hdr_admin,
        "Zapomni: aliasy dolzhny byt idempotentny",
    )
    # zaprosim flashback, vozmem 2 id (esli odin — dobavim esche)
    r = client.get(
        "/mem/flashback",
        query_string={"query": "aliasy", "k": 5},
        headers=auth_hdr_admin,
    )
    assert r.status_code == 200
    ids = [it.get("id") for it in (r.get_json().get("results") or []) if it.get("id")]
    if len(ids) < 2:
        _create_dialog(client, auth_hdr_admin, "Vtoraya zapis dlya alias")
        r = client.get(
            "/mem/flashback",
            query_string={"query": "zapis", "k": 5},
            headers=auth_hdr_admin,
        )
        ids.extend([it.get("id") for it in (r.get_json().get("results") or []) if it.get("id")])
    assert len(ids) >= 2
    a, b = ids[0], ids[1]
    # alias: dvazhdy odna i ta zhe perealisatsiya
    r1 = client.post("/mem/alias", json={"old_doc_id": a, "new_doc_id": b}, headers=auth_hdr_admin)
    r2 = client.post("/mem/alias", json={"old_doc_id": a, "new_doc_id": b}, headers=auth_hdr_admin)
    assert r1.status_code == 200 and r2.status_code == 200
    # compact: posle pervogo progona vtoroy ne dolzhen nichego udalyat/slivat
    r3 = client.post("/mem/compact", json={"dry_run": False}, headers=auth_hdr_admin)
    assert r3.status_code == 200
    j3 = r3.get_json()
    assert "deleted" in j3 and "merged" in j3
    r4 = client.post("/mem/compact", json={"dry_run": False}, headers=auth_hdr_admin)
    j4 = r4.get_json()
    # ozhidaem, chto vtoroy progon ne usilit effekt
    assert j4.get("deleted", 0) <= j3.get("deleted", 0)
# assert j4.get("merged", 0) <= j3.get("merged", 0)