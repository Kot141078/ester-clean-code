# -*- coding: utf-8 -*-
import types
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_replicate_daemon_one_tick_success(monkeypatch):
    import scripts.replicate_daemon as rd

    class R1:
        headers = {"X-Signature": "sig123"}
        content = b"ZIPDATA"

    class R2:
        status_code = 200

    # podmenim requests v p2p_replicator
    import p2p_replicator

    def fake_get(url, headers=None, timeout=None):
        return R1()

    def fake_post(url, headers=None, data=None, timeout=None):
        return R2()

    monkeypatch.setattr(
        p2p_replicator, "requests", types.SimpleNamespace(get=fake_get, post=fake_post)
    )

    # peers/token
    monkeypatch.setenv("REPLICATION_PEERS", "http://peer1.local")
    monkeypatch.setenv("REPLICATION_TOKEN", "secret")

    rep = rd.one_tick()
    assert rep.get("ok") is True
# assert isinstance(rep.get("report"), dict)