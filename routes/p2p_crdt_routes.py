# -*- coding: utf-8 -*-
"""CRDT P2P routes used by tests and local ops tools."""
from __future__ import annotations

import os
import socket
from typing import Any, Dict, Iterable, List

from flask import Blueprint, jsonify, request

try:
    from flask_jwt_extended import get_jwt, jwt_required  # type: ignore
except Exception:  # pragma: no cover
    def jwt_required(*_a, **_kw):  # type: ignore
        def _wrap(fn):
            return fn

        return _wrap

    def get_jwt() -> Dict[str, Any]:  # type: ignore
        return {}

from crdt.lww_set import LwwSet
from crdt.types import Item, LwwEntry
from merkle.merkle_tree import Merkle
from p2p.merkle_branch import branch_slices
from p2p.merkle_sync import entry_fingerprint

bp = Blueprint("p2p_crdt", __name__)


def _env_true(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _roles_from_claims() -> set[str]:
    try:
        claims = get_jwt() or {}
    except Exception:
        claims = {}
    roles = claims.get("roles") or claims.get("role") or []
    if isinstance(roles, str):
        roles = [roles]
    out: set[str] = set()
    if isinstance(roles, Iterable):
        for r in roles:
            rs = str(r).strip().lower()
            if rs:
                out.add(rs)
    return out


def _serialize_entry(e: LwwEntry) -> Dict[str, Any]:
    return {
        "item": {"id": e.item.id, "payload": dict(e.item.payload or {})},
        "add": ({"peer": e.add.peer, "ts": int(e.add.ts)} if e.add else None),
        "rem": ({"peer": e.rem.peer, "ts": int(e.rem.ts)} if e.rem else None),
    }


def _build_levels(entries: Dict[str, LwwEntry]) -> tuple[List[str], str, List[List[str]]]:
    leaf_ids = sorted(entries.keys())
    leaves = [entry_fingerprint(iid, entries[iid]) for iid in leaf_ids]
    root, levels = Merkle.build(leaves)
    return leaf_ids, root, levels


class CRDT:
    peer_id: str = (os.getenv("ESTER_PEER_ID") or socket.gethostname() or "peer-local").strip()
    _set: LwwSet = LwwSet(peer_id=peer_id)
    clock: int = 0
    entries: Dict[str, LwwEntry] = _set.entries

    @classmethod
    def _sync_view(cls) -> None:
        cls.clock = int(cls._set.clock)
        cls.entries = cls._set.entries

    @classmethod
    def add(cls, item: Item) -> Dict[str, Any]:
        dot = cls._set.add(item)
        cls._sync_view()
        return {"peer": dot.peer, "ts": int(dot.ts)}

    @classmethod
    def remove(cls, item_id: str) -> Dict[str, Any]:
        dot = cls._set.remove(item_id)
        cls._sync_view()
        return {"peer": dot.peer, "ts": int(dot.ts)}

    @classmethod
    def import_op(cls, op: str, item_id: str, data: Dict[str, Any]) -> None:
        cls._set.import_op(op, item_id, data)
        cls._sync_view()

    @classmethod
    def visible_items(cls) -> List[Dict[str, Any]]:
        vis = cls._set.visible_items()
        return [{"id": iid, "payload": dict(item.payload or {})} for iid, item in vis.items()]

    @classmethod
    def visible_count(cls) -> int:
        return len(cls._set.visible_items())

    @staticmethod
    def merge(a: Dict[str, Any] | None, b: Dict[str, Any] | None) -> Dict[str, Any]:
        return {**(a or {}), **(b or {})}


CRDT._sync_view()


@bp.get("/p2p/state")
@jwt_required(optional=True)
def p2p_state():
    try:
        level = int(request.args.get("level", "0") or "0")
    except Exception:
        return jsonify({"ok": False, "error": "bad_level"}), 400
    if level < 0:
        return jsonify({"ok": False, "error": "bad_level"}), 400

    leaf_ids, root, levels = _build_levels(CRDT.entries)
    if level >= len(levels):
        level_hashes: List[str] = []
    else:
        level_hashes = list(levels[level])

    return jsonify(
        {
            "ok": True,
            "peer_id": CRDT.peer_id,
            "clock": int(CRDT.clock),
            "root": root,
            "level_index": level,
            "level": level_hashes,
            "levels_count": len(levels),
            "leaf_ids": leaf_ids,
        }
    )


@bp.get("/p2p/state_branch")
@jwt_required(optional=True)
def p2p_state_branch():
    try:
        start = int(request.args.get("start", "0") or "0")
        end = int(request.args.get("end", "0") or "0")
    except Exception:
        return jsonify({"ok": False, "error": "bad_window"}), 400

    leaf_ids, root, levels = _build_levels(CRDT.entries)
    try:
        branches = branch_slices(levels, start, end)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify(
        {
            "ok": True,
            "peer_id": CRDT.peer_id,
            "clock": int(CRDT.clock),
            "root": root,
            "start": start,
            "end": end,
            "leaf_ids": leaf_ids[start:end],
            "branches": branches,
        }
    )


@bp.post("/p2p/mem/add")
@jwt_required()
def p2p_mem_add():
    data = request.get_json(force=True, silent=True) or {}
    iid = str(data.get("id") or "").strip()
    payload = data.get("payload")
    if not iid:
        return jsonify({"ok": False, "error": "id_required"}), 400
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "payload_required"}), 400
    dot = CRDT.add(Item(id=iid, payload=payload))
    return jsonify({"ok": True, "id": iid, "dot": dot})


@bp.post("/p2p/pull_by_ids")
@jwt_required()
def p2p_pull_by_ids():
    data = request.get_json(force=True, silent=True) or {}
    ids = data.get("ids") or []
    if not isinstance(ids, list):
        return jsonify({"ok": False, "error": "ids_must_be_list"}), 400

    out: Dict[str, Dict[str, Any]] = {}
    for raw in ids:
        iid = str(raw or "").strip()
        if not iid:
            continue
        e = CRDT.entries.get(iid)
        if e is not None:
            out[iid] = _serialize_entry(e)
    return jsonify({"ok": True, "entries": out})


@bp.post("/p2p/push")
@jwt_required()
def p2p_push():
    strict = _env_true("ESTER_RBAC_STRICT", False)
    if strict:
        roles = _roles_from_claims()
        if not (roles & {"replicator", "admin", "operator"}):
            return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(force=True, silent=True) or {}
    ops = data.get("ops") or []
    if not isinstance(ops, list):
        return jsonify({"ok": False, "error": "ops_must_be_list"}), 400

    applied = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or op.get("kind") or "").strip().lower()
        iid = str(op.get("id") or op.get("item_id") or "").strip()
        if not iid or kind not in {"add", "rem"}:
            continue
        payload = op.get("payload")
        data_obj = op.get("data")
        if not isinstance(data_obj, dict):
            data_obj = {}
        if kind == "add":
            dot_obj = data_obj.get("dot")
            if not isinstance(dot_obj, dict):
                data_obj["dot"] = {"peer": CRDT.peer_id, "ts": int(CRDT.clock) + 1}
            if payload is not None and "payload" not in data_obj:
                data_obj["payload"] = payload
        try:
            CRDT.import_op(kind, iid, data_obj)
            applied += 1
        except Exception:
            continue

    return jsonify({"ok": True, "applied": applied, "clock": int(CRDT.clock)})


def register(app):
    if bp.name in app.blueprints:
        return app
    app.register_blueprint(bp)
    return app
