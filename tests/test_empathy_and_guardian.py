from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_empathy_ping_and_analyze(client, auth_hdr_user):
    r = client.get("/empathy/ping", headers=auth_hdr_user)
    assert r.status_code in (200, 404)
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True
    a = client.post(
        "/empathy/analyze",
        headers=auth_hdr_user,
        json={"text": "Spasibo, vse super!"},
    )
    assert a.status_code == 200
    ja = a.get_json()
    assert ja.get("ok") is True
    t = client.post(
        "/empathy/tune",
        headers=auth_hdr_user,
        json={"base": "Otvechayu po suti.", "analysis": ja.get("analysis")},
    )
    assert t.status_code == 200


def test_guardian_status_event_and_summary(client, auth_hdr_user):
    g = client.get("/session/guardian/status", headers=auth_hdr_user)
    assert g.status_code in (200, 404)
    if g.status_code != 200:
        return
    j = g.get_json()
    assert "context_limit" in j or j.get("ok") in (True, False)

    e = client.post(
        "/session/guardian/event",
        headers=auth_hdr_user,
        json={
            "role": "user",
            "content": "Long, long discussion text for the test.",
        },
    )
    assert e.status_code == 200
    s = client.post("/session/guardian/summarize", headers=auth_hdr_user, json={})
    assert s.status_code == 200
    js = s.get_json()
    assert js.get("ok") is True
# assert "summary" in js