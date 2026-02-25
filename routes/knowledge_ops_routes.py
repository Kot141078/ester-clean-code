# -*- coding: utf-8 -*-
"""routes/knowledge_ops_routes.py - REST/UI dlya "kukhni znaniy".

Ruchki (JSON):
  POST /knowledge/source/add {"url":"...","title":"...","meta":{...}}
  GET /knowledge/source/list
  POST /knowledge/source/update {"id":"...","title?":...,"score?":...,"meta?":{...}}
  POST /knowledge/source/remove {"id":"..."}
  POST /knowledge/source/touch {"id":"...","ok":true,"bytes":12345}

  POST /knowledge/evidence/build {"query":"...","top_k":12} | {"record_id":"..."}
  POST /knowledge/evidence/cite {"query":"..."} | {"record_id":"..."}
  POST /knowledge/answer/passport {"answer":"...","query":"..."} | {"answer":"...","record_id":"..."}

  POST /knowledge/ingest/sample {} # sozdaet neskolko zapisey dlya demonstratsii
  POST /knowledge/dedup/run {"top_k":200}

  GET /admin/knowledge_ops

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.knowledge import registry as REG
from modules.knowledge import quality as Q
from modules.knowledge import cite as CIT
from modules.memory import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("knowledge_ops_routes", __name__, url_prefix="/knowledge")

# sources
@bp.route("/source/add", methods=["POST"])
def source_add():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(REG.add_source(d.get("url",""), d.get("title",""), d.get("meta") or {}))

@bp.route("/source/list", methods=["GET"])
def source_list():
    return jsonify(REG.list_sources())

@bp.route("/source/update", methods=["POST"])
def source_update():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(REG.update_source(d.get("id",""), d))

@bp.route("/source/remove", methods=["POST"])
def source_remove():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(REG.remove_source(d.get("id","")))

@bp.route("/source/touch", methods=["POST"])
def source_touch():
    d=request.get_json(force=True,silent=True) or {}
    return jsonify(REG.touch_source(d.get("id",""), bool(d.get("ok",True)), int(d.get("bytes",0))))

# evidence / cite / passport
@bp.route("/evidence/build", methods=["POST"])
def evidence_build():
    d=request.get_json(force=True,silent=True) or {}
    if d.get("record_id"):
        return jsonify(CIT.build_evidence_pack(record_id=d["record_id"]))
    return jsonify(CIT.build_evidence_pack(record_id=None, query=d.get("query",""), top_k=int(d.get("top_k",12))))

@bp.route("/evidence/cite", methods=["POST"])
def evidence_cite():
    d=request.get_json(force=True,silent=True) or {}
    pack = CIT.build_evidence_pack(record_id=d.get("record_id"), query=d.get("query"))
    return jsonify(CIT.cite_lines(pack))

@bp.route("/answer/passport", methods=["POST"])
def answer_passport():
    d=request.get_json(force=True,silent=True) or {}
    pack = CIT.build_evidence_pack(record_id=d.get("record_id"), query=d.get("query"))
    return jsonify(CIT.answer_passport(d.get("answer",""), pack))

# ingest & dedup (demo)
@bp.route("/ingest/sample", methods=["POST"])
def ingest_sample():
    # create several records linked to the source (if any)
    items=[]
    src = REG.list_sources().get("items", [])
    src_id = src[0]["id"] if src else "mem"
    for t in [
        "File ProjectPlan.md: goals, deadlines, metrics. Plan for the week.",
        "Grajs Anatomy: determination of liver structure and blood supply.",
        "Dhammapada: a brief summary - ways to overcome suffering.",
        "Repeat: Weekly plan (same content)."
    ]:
        r=memory_add("fact", t, {"source_id":src_id})
        items.append(r)
    return jsonify({"ok":True,"count":len(items),"source_id":src_id})

@bp.route("/dedup/run", methods=["POST"])
def dedup_run():
    d=request.get_json(force=True,silent=True) or {}
    top=int(d.get("top_k",200))
    items=sorted(store._MEM.values(), key=lambda r:r.get("ts",0), reverse=True)[:top]
    res=Q.dedup_records(items)
    return jsonify({"ok":True,"kept":len(res["kept"]),"dropped":len(res["dropped"]),"ratio":res["ratio"]})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_knowledge_ops.html")

def register(app):
    app.register_blueprint(bp)