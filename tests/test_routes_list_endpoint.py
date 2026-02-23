from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_routes_listing_smoke():
    from app import app as flask_app
    c = flask_app.test_client()
    r = c.get("/routes")
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, dict)
    assert "routes" in j and isinstance(j["routes"], list)
    # v spiske dolzhen byt khotya by odin put
    assert len(j["routes"]) > 0