# -*- coding: utf-8 -*-
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _make_dialog(client, hdr, text="Eto testovyy dialog"):
    r = client.post("/chat/message", json={"query": text, "use_rag": False}, headers=hdr)
    assert r.status_code == 200


def test_flashback_alias_compact(client, auth_hdr_user):
    # Sozdaem zapis dialoga
    _make_dialog(client, auth_hdr_user, "Zapomni eto vazhnoe soobschenie")

    # Ischem fleshbek
    r = client.get("/mem/flashback", query_string={"query": "vazhnoe"}, headers=auth_hdr_user)
    assert r.status_code == 200, r.data
    j = r.get_json()
    assert j.get("results"), "Ozhidalis rezultaty flashback"
    first = j["results"][0]
    assert "id" in first

    # alias
    doc_id = first["id"]
    r2 = client.post(
        "/mem/alias",
        json={"doc_id": doc_id, "alias": doc_id + "_alias"},
        headers=auth_hdr_user,
    )
    assert r2.status_code == 200, r2.data

    # compact (dry_run)
    r3 = client.post("/mem/compact", json={"dry_run": True}, headers=auth_hdr_user)
    assert r3.status_code == 200
    j3 = r3.get_json()
# assert "deleted" in j3 and "merged" in j3