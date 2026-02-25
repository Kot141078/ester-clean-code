# -*- coding: utf-8 -*-
import os
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from p2p_replicator import PeerReplicator
from routes_replication import register_replication_routes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

REPL_TOKEN = "test-repl-token"


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Prepare the structure of “node A” (snapshot source)
    src_root = tmp_path / "nodeA"
    (src_root / "data" / "vstore").mkdir(parents=True)
    (src_root / "data" / "vstore" / "vec.bin").write_bytes(b"\x00\x01\x02")

    # Prilozhenie
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["JWT_SECRET_KEY"] = "test-secret"
    jwt = JWTManager(app)

    # ENV for snapshot
    monkeypatch.setenv("REPLICATION_TOKEN", REPL_TOKEN)
    monkeypatch.setenv("REPLICATION_INCLUDE_DIRS", "data")

    # Replikator
    replicator = PeerReplicator(peers=[], token=REPL_TOKEN, interval_sec=1)
    register_replication_routes(app, replicator)

    # Go to srts_root so that the snapshot can be collected from it
    monkeypatch.chdir(src_root)

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(app):
    with app.app_context():
        token = create_access_token(identity="tester")
    return {"Authorization": f"Bearer {token}"}


def test_snapshot_and_apply_flow(client, tmp_path, monkeypatch):
    # 1) Peer A: snapshot request
    r = client.get("/replication/snapshot", headers={"X-REPL-TOKEN": REPL_TOKEN})
    assert r.status_code == 200
    assert r.headers.get("X-Signature")
    blob = r.data
    sig = r.headers["X-Signature"]

    # 2) Switch the working directory to “node B” and use a snapshot
    dst_root = tmp_path / "nodeB"
    dst_root.mkdir()
    monkeypatch.chdir(dst_root)

    r2 = client.post(
        "/replication/apply",
        data=blob,
        headers={"X-REPL-TOKEN": REPL_TOKEN, "X-Signature": sig},
    )
    assert r2.status_code == 200
    stats = r2.get_json()["stats"]
    assert stats["files"] >= 1
    assert (dst_root / "data" / "vstore" / "vec.bin").exists()


def test_status_and_pull_now(client, auth_header, monkeypatch):
    # pull_now dergaet replicator.pull_once — on ne delaet setevye vyzovy v teste
    r = client.get("/replication/status", headers=auth_header)
    assert r.status_code == 200
    st = r.get_json()
    assert "peers" in st and "running" in st

    r2 = client.post("/replication/pull_now", headers=auth_header)
    assert r2.status_code == 200
    rep = r2.get_json()["report"]
    # On an empty list of peers, just an empty report
    assert "pulled" in rep
