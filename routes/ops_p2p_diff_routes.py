# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import jwt_required  # type: ignore

from p2p.merkle_sync import diff_by_leaves, local_leaf_hashes
from p2p.sync_client import pull_by_ids, state_level
from routes.p2p_crdt_routes import CRDT  # lokalnyy CRDT
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ops_p2p_diff = Blueprint("ops_p2p_diff", __name__, template_folder="../templates")


@bp_ops_p2p_diff.get("/ops/p2p/diff")
@jwt_required(optional=True)
def ops_p2p_diff_page():
    return render_template("ops_p2p_diff.html")


@bp_ops_p2p_diff.post("/ops/p2p/diff/json")
@jwt_required(optional=True)
def ops_p2p_diff_json():
    """Body of option A (remote peer):
      ZZF0Z
    Option B (without network, for tests/simulation):
      ZZF1ZZ

    Answer:
      ZZF2ZZ"""
    data = request.get_json(force=True, silent=True) or {}
    local_map = local_leaf_hashes(CRDT)

    leaf_ids: List[str]
    leaf_hashes: List[str]

    if "peer" in data:
        st = state_level(str(data["peer"]), level=0)
        if not st.get("ok"):
            return (
                jsonify({"ok": False, "err": st.get("error") or st.get("status")}),
                502,
            )
        leaf_ids = list(st.get("leaf_ids") or [])
        leaf_hashes = list(st.get("level") or [])
    else:
        leaf_ids = list(data.get("leaf_ids") or [])
        leaf_hashes = list(data.get("leaf_hashes") or [])
        if not leaf_ids or not leaf_hashes or len(leaf_ids) != len(leaf_hashes):
            return jsonify({"ok": False, "err": "bad input: leaf_ids/leaf_hashes"}), 400

    need_ids = diff_by_leaves(local_map, leaf_ids, leaf_hashes)
    return jsonify(
        {
            "ok": True,
            "diff_ids": need_ids,
            "local_count": len(local_map),
            "remote_count": len(leaf_ids),
        }
    )


@bp_ops_p2p_diff.post("/ops/p2p/diff/fetch")
@jwt_required()  # splash protection
def ops_p2p_diff_fetch():
    """Takes “fat” records from a remote peer according to a list of ids (followed by local logic).
    Body: ZZF0Z"""
    d = request.get_json(force=True, silent=True) or {}
    peer = str(d.get("peer") or "")
    ids: List[str] = list(d.get("ids") or [])
    if not peer or not ids:
        return jsonify({"ok": False, "err": "peer and ids are required"}), 400
    r = pull_by_ids(peer, ids)
    return jsonify(r), (200 if r.get("ok") else 502)


def register(app):
    app.register_blueprint(bp_ops_p2p_diff)
    return app
