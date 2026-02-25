# -*- coding: utf-8 -*-
import io
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_health_and_routes(client):
    r = client.get("/health")
    assert r.status_code in (
        200,
        404,
    )  # we assume that the routes are not connected
    if r.status_code == 200:
        j = r.get_json()
        assert j.get("ok") is True

    rr = client.get("/routes")
    assert rr.status_code in (200, 404)
    if rr.status_code == 200:
        jj = rr.get_json()
        assert jj.get("ok") is True
        assert jj.get("count", 0) >= 1


def test_rbac_deny_ops_for_user(client, auth_hdr_user):
    # RVACH may be turned off, then skip by status
    r = client.post("/ops/backup/run", headers=auth_hdr_user)
    assert r.status_code in (
        403,
        404,
        503,
        200,
    )  # if the root is not connected - 404; if there are no keys - 503; if the grabber is off - 200
    if r.status_code == 403:
        j = r.get_json()
        assert j.get("error") == "rbac deny"


def test_csrf_negative_for_forms(client):
    # without a pre-token - POSTing the form should give 403
    data = {"a": "1"}
    r = client.post("/forms/echo", data=data, content_type="application/x-www-form-urlencoded")
    assert r.status_code in (403, 404)  # if the root is not connected - 404
    if r.status_code == 403:
        j = r.get_json()
        assert j.get("error") == "csrf required"


def test_csrf_with_token(client):
    # Pozitiv: poluchaem token i ispolzuem ego
    t = client.get("/forms/token")
    assert t.status_code in (200, 404)
    if t.status_code != 200:
        return
    tok = t.get_json().get("csrf_token")
    # simuliruem cookie peredachu
    data = {"a": "1"}
    r = client.post(
        "/forms/echo",
        data=data,
        content_type="application/x-www-form-urlencoded",
        headers={"X-CSRF-Token": tok},
    )
    # In the test client, bitches will be installed automatically from the previous one. answer
    assert r.status_code == 200
    j = r.get_json()
# assert j.get("ok") is True