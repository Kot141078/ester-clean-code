import json

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

import modules.kg_beacons_query as kg_beacons
from routes.beacons_routes import register_beacons_routes


def test_list_beacons_accepts_since_and_kinds_filters(tmp_path, monkeypatch):
    store = tmp_path / "beacons.json"
    store.write_text(
        json.dumps(
            {
                "beacons": [
                    {"id": "old", "kind": "backup.done", "ts": 10, "label": "Old"},
                    {"id": "new", "kind": "scheduler:tick", "ts": 20, "label": "New"},
                    {"id": "other", "kind": "backup.done", "ts": 30, "label": "Other"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(kg_beacons, "BEACONS_DB", str(store))

    rows = kg_beacons.list_beacons(limit=10, since=15, kinds=["backup.done"])

    assert [row["id"] for row in rows] == ["other"]
    assert rows[0]["kind"] == "backup.done"
    assert rows[0]["ts"] == 30.0


def test_beacons_stats_accepts_route_filter_signature(tmp_path, monkeypatch):
    store = tmp_path / "beacons.json"
    store.write_text(
        json.dumps(
            {
                "items": [
                    {"id": "a", "kind": "backup.done", "ts": 1},
                    {"id": "b", "kind": "backup.done", "ts": 2},
                    {"id": "c", "kind": "scheduler:tick", "ts": 3},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(kg_beacons, "BEACONS_DB", str(store))

    stats = kg_beacons.beacons_stats(limit=10, since=2, kinds=["backup.done"])

    assert stats["ok"] is True
    assert stats["beacons"] == 1
    assert stats["stored_beacons"] == 3
    assert stats["kinds"] == ["backup.done"]


def test_beacons_stats_route_returns_json(tmp_path, monkeypatch):
    store = tmp_path / "beacons.json"
    store.write_text(
        json.dumps({"beacons": [{"id": "a", "kind": "backup.done", "ts": 10}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(kg_beacons, "BEACONS_DB", str(store))

    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = "test-secret"
    JWTManager(app)
    register_beacons_routes(app)
    with app.app_context():
        token = create_access_token(identity="pytest")

    response = app.test_client().get(
        "/beacons/stats?limit=10&since=5",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["beacons"] == 1
