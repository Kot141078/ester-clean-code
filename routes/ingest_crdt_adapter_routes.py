# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules.storage.vector_crdt_adapter import VectorCRDTAdapter  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ingest_crdt_adapter = Blueprint("ingest_crdt_adapter", __name__)


def _require_fields(d: Dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise KeyError("missing fields: " + ",".join(missing))


@bp_ingest_crdt_adapter.post("/ingest/crdt/put")
@jwt_required()
def ingest_put():
    """
    Prinimaet: {"id": "<string>", "payload": {..lyuboy obekt pamyati..}}
    Sokhranyaet payload v CAS (cid), a v CRDT — legkuyu metu Re pointer na CAS.
    Bozvraschaet {"ok": true, "id": ..., "cid": ..., "meta": {...}}
    """
    data = request.get_json(force=True, silent=True) or {}
    _require_fields(data, ["id", "payload"])
    adapter = VectorCRDTAdapter()
    res = adapter.put(str(data["id"]), dict(data["payload"]))
    return jsonify({"ok": True, **res})


@bp_ingest_crdt_adapter.get("/ingest/crdt/fetch")
@jwt_required(optional=True)
def ingest_fetch():
    """
    Chitaet obedinennyy obekt iz CRDT+CAS.
    Parametry: ?id=<string>
    """
    item_id = request.args.get("id", type=str)
    if not item_id:
        return jsonify({"ok": False, "err": "id is required"}), 400
    adapter = VectorCRDTAdapter()
    obj = adapter.fetch(item_id)
    if obj is None:
        return jsonify({"ok": False, "err": "not found"}), 404
    return jsonify({"ok": True, "result": obj})


@bp_ingest_crdt_adapter.delete("/ingest/crdt/rem")
@jwt_required()
def ingest_remove():
    """
    Logicheskoe udalenie zapisi (remove v CRDT). CAS-bloki ostayutsya deduplitsirovannymi.
    Telo: {"id": "<string>"}
    """
    data = request.get_json(force=True, silent=True) or {}
    _require_fields(data, ["id"])
    adapter = VectorCRDTAdapter()
    adapter.remove(str(data["id"]))
    return jsonify({"ok": True})


def register(app):
    app.register_blueprint(bp_ingest_crdt_adapter)
    return app
