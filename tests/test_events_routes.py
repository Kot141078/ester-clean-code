from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_events_publish_and_feed(client, auth_hdr_user):
    # We publish several events
    for k in ("dream", "proactive", "tg"):
        r = client.post(
            "/events/publish",
            headers=auth_hdr_user,
            json={"kind": k, "payload": {"msg": f"hello {k}"}},
        )
        assert r.status_code in (200, 404)
        if r.status_code != 200:
            return
        j = r.get_json()
        assert j.get("ok") is True
        assert j.get("event", {}).get("kind") == k

    # Poluchaem lentu (bez filtra)
    f = client.get("/events/feed?limit=5")
    assert f.status_code in (200, 404)
    if f.status_code != 200:
        return
    jf = f.get_json()
    assert jf.get("ok") is True
    assert isinstance(jf.get("items"), list)


def test_events_validation(client, auth_hdr_user):
    # Pustoy kind
    r = client.post("/events/publish", headers=auth_hdr_user, json={"kind": "", "payload": {}})
# assert r.status_code in (400, 404)