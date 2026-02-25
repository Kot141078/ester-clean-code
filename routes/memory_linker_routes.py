# -*- coding: utf-8 -*-
"""routes/memory_linker_routes.py - linkovka kartochek pamyati k suschnostyam (1 klik).

MOSTY:
- (Yavnyy) POST /mem/linker/link {doc_id, entity_id, entity_type, rel}
- (Skrytyy #1) POST /mem/linker/create_entity {type, name, attrs} - bystryy upsert i vozvrat id.
- (Skrytyy #2) Obnovlyaet entity.links i sozdaet "edge" v pamyati (semantic) bez izmeneniya starykh kontraktov.

ZEMNOY ABZATs:
“Stepler” mezhdu kartotekoy i zapisnoy knizhkoy: svyazali zametku s personoy - dalshe vse nakhoditsya mgnovenno.

# c=a+b"""
from __future__ import annotations
import os, json, time, uuid, re
from typing import Dict, Any, List
from flask import Blueprint, request, jsonify
from modules.memory.layers import get as mem_get, store as mem_store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_linker_routes", __name__, url_prefix="/mem/linker")

def register(app):
    app.register_blueprint(bp)

BASE = os.path.join("data", "mem", "entities")
os.makedirs(BASE, exist_ok=True)

def _safe_type(t: str) -> str:
    t = (t or "doc").lower()
    if not re.match(r"^[a-z0-9_\-]+$", t):
        t = "doc"
    return t

def _edir(t: str) -> str:
    p = os.path.join(BASE, t)
    os.makedirs(p, exist_ok=True)
    return p

def _epath(t: str, _id: str) -> str:
    return os.path.join(_edir(t), f"{_id}.json")

@bp.post("/create_entity")
def create_entity():
    data = request.get_json(silent=True) or {}
    t = _safe_type(str(data.get("type","doc")))
    name = (data.get("name") or "").strip()
    attrs = data.get("attrs") or {}
    _id = data.get("id") or str(uuid.uuid4())
    body = {"id": _id, "type": t, "name": name, "attrs": attrs, "links": [], "ts": time.time()}
    with open(_epath(t, _id), "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False)
    return jsonify({"ok": True, "entity": body})

@bp.post("/link")
def link():
    data = request.get_json(silent=True) or {}
    doc_id = (data.get("doc_id") or "").strip()
    ent_id = (data.get("entity_id") or "").strip()
    ent_type = _safe_type(str(data.get("entity_type","doc")))
    rel = (data.get("rel") or "mentions").strip().lower()

    if not doc_id or not ent_id:
        return jsonify({"ok": False, "error": "doc_id/entity_id required"}), 400

    doc = mem_get(doc_id)
    if not doc:
        return jsonify({"ok": False, "error": "doc not found"}), 404

    p = _epath(ent_type, ent_id)
    if not os.path.isfile(p):
        return jsonify({"ok": False, "error": "entity not found"}), 404

    # 1) update entity.links
    with open(p, "r", encoding="utf-8") as f:
        ent = json.load(f)
    links: List[Dict[str,Any]] = ent.get("links") or []
    if not any((l.get("doc_id")==doc_id and l.get("rel")==rel) for l in links):
        links.append({"doc_id": doc_id, "rel": rel, "ts": time.time()})
        ent["links"] = links
        with open(p, "w", encoding="utf-8") as f:
            json.dump(ent, f, ensure_ascii=False)

    # 2) create a semantic “edge” in memory
    edge = mem_store("semantic", f"edge:entity:{ent_id}::{rel}::doc:{doc_id}", {
        "a": f"entity:{ent_type}:{ent_id}",
        "b": f"doc:{doc_id}",
        "rel": rel,
        "entity_name": ent.get("name",""),
        "doc_kind": doc.get("kind","note"),
    })

    return jsonify({"ok": True, "entity": {"id": ent_id, "type": ent_type}, "doc": {"id": doc_id}, "edge": edge})
# c=a+b