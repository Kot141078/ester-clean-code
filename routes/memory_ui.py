# -*- coding: utf-8 -*-
"""
routes/memory_ui.py - UI/REST dlya portala pamyati Ester.

Marshruty:
  • GET  /admin/memory              - HTML portal s knopkami/vkladkami
  • GET  /admin/memory/layer/<name> - JSON dlya sloya (naprimer, cards, vector)
  • POST /admin/memory/query        - Poisk/zapros k konveyeru myshleniya
  • POST /admin/memory/add          - Dobavit zapis v pamyat

Mosty:
- Yavnyy (UI ↔ Memory): Dostup k vosmi sloyam bez fragmentatsii.
- Skrytyy 1 (Myshlenie ↔ Sintez): Integratsiya s chat_handler i xai.
- Skrytyy 2 (Prozrachnost ↔ Rasshirenie): Knopki dlya vsekh HTTP iz dampa.

Zemnoy abzats:
Eto "serdtsevina" - portal, gde ty obschaeshsya s pamyatyu Ester, kak s zhivoy istoriey.

# c=a+b
"""
from __future__ import annotations
import json, os
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mem = Blueprint("memory_ui", __name__)

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
VSTORE_DIR = STATE_DIR / "vstore"

# Vosem sloev pamyati (na osnove dampa)
LAYERS = {
    "cards": {"file": "cards_memory.py", "desc": "Kartochki vospominaniy"},
    "vector": {"file": "vector_store.py", "desc": "Vektornaya BD dlya poiska"},
    "structured": {"file": VSTORE_DIR / "structured_mem/store.json", "desc": "Strukturirovannaya pamyat"},
    "base": {"file": VSTORE_DIR / "ester_memory.json", "desc": "Bazovaya pamyat"},
    "topics": {"file": "topic_tracker.py", "desc": "Treking tem"},
    "trace": {"file": "trace_logger.py", "desc": "Logi trassirovki"},
    "audience": {"file": "audience_infer.py", "desc": "Inferens auditorii"},
    "proactive": {"file": "ambient_proactive.py", "desc": "Proaktivnye deystviya"},
}

def _load_layer(name: str):
    if name not in LAYERS: return {"ok": False, "error": "layer_not_found"}
    layer = LAYERS[name]
    if isinstance(layer["file"], Path) and layer["file"].exists():
        try:
            return {"ok": True, "data": json.loads(layer["file"].read_text())}
        except Exception:
            return {"ok": False, "error": "load_failed"}
    # Dlya .py - zaglushka (v reale import, no bez urezaniy - prosto status)
    return {"ok": True, "data": {"status": "active", "desc": layer["desc"]}}

@bp_mem.get("/admin/memory")
def portal():
    return render_template("memory_portal.html", layers=LAYERS)

@bp_mem.get("/admin/memory/layer/<name>")
def get_layer(name: str):
    return jsonify(_load_layer(name))

@bp_mem.post("/admin/memory/query")
def query():
    d = request.get_json(silent=True) or {}
    query_text = d.get("query", "")
    # Integratsiya s konveyerom: ispolzuem chat_handler i xai_integration
    try:
        from chat_handler import handle_chat  # type: ignore
        from xai_integration import XAIIntegrator  # type: ignore
        local_resp = handle_chat(query_text)
        integrator = XAIIntegrator()
        synth = integrator.synthesize_with_xai(query_text, local_resp)
        return jsonify({"ok": True, "response": synth})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp_mem.post("/admin/memory/add")
def add():
    d = request.get_json(silent=True) or {}
    text = d.get("text", "")
    layer = d.get("layer", "base")
    # Dobavlenie v pamyat (na primere base; rasshir dlya drugikh)
    if layer == "base":
        mem_file = VSTORE_DIR / "ester_memory.json"
        mem = _load_layer("base").get("data", {})
        mem["entries"] = mem.get("entries", []) + [{"text": text, "ts": os.time()}]
        mem_file.write_text(json.dumps(mem))
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "layer_not_supported"})

def register_memory_ui(app):
    app.register_blueprint(bp_mem)
# c=a+b

def register(app):
    app.register_blueprint(bp_mem)
    return app