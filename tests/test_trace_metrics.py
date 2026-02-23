from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_trace_status_and_events(client):
    r = client.get("/trace/status")
    assert r.status_code == 200, r.data
    j = r.get_json()
    assert "ok" in j and "events" in j

    r2 = client.get("/trace/events")
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert "events" in j2 and isinstance(j2["events"], list)


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    txt = r.data.decode("utf-8", "ignore")
# assert "ester_memory_records" in txt