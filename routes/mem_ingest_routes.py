# -*- coding: utf-8 -*-
"""
routes/mem_ingest_routes.py - ingest tekstov/faylov v pamyat.

MOSTY:
- (Yavnyy) POST /mem/ingest/text i POST /mem/ingest/file (multipart/form-data).
- (Skrytyy #1) Fayly sokhranyayutsya v data/uploads; tekstovye izvlekayutsya i idut v sloi pamyati.
- (Skrytyy #2) Bez vneshnikh parserov; bezopasnyy porog chteniya (<=1 MB), metki v meta.

ZEMNOY ABZATs:
Okoshko «Polozhit dokument»: brosil fayl - on i sokhranilsya, i popal v kartoteku dlya poiska.

# c=a+b
"""
from __future__ import annotations
import os, time
from flask import Blueprint, request, jsonify
from modules.memory.layers import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_ingest_routes", __name__, url_prefix="/mem/ingest")

def register(app):
    app.register_blueprint(bp)

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_READ = 1_000_000  # 1MB

@bp.post("/text")
def ingest_text():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    kind = (data.get("kind") or "doc").strip()
    meta = data.get("meta") or {}
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400
    doc = store(kind, text, {"source":"ingest/text", **meta})
    return jsonify({"ok": True, "doc": doc})

@bp.post("/file")
def ingest_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "file required"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "empty filename"}), 400
    safe_name = f.filename.replace("..","_").replace("\\","/").split("/")[-1]
    path = os.path.join(UPLOAD_DIR, f"{int(time.time())}_{safe_name}")
    f.save(path)

    # Poprobuem prochest kak tekst (best effort)
    text = ""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(MAX_READ)
        text = chunk.decode("utf-8", errors="ignore")
    except Exception:
        text = ""

    doc = None
    if text.strip():
        doc = store("doc", text[:MAX_READ], {"source":"ingest/file", "filename": safe_name})

    return jsonify({"ok": True, "saved": path, "doc": doc})
# c=a+b