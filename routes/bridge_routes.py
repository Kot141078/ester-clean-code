# -*- coding: utf-8 -*-
"""routes/bridge_routes.py - REST/UI dlya Personal↔Global Bridge.

MOSTY:
- Yavnyy: (UI ↔ Bridge) /bridge/query - edinaya tochka poiska po pamyati i globali.
- Skrytyy #1: (Memory ↔ KG) esli est modules.memory.layers.search - addvlyaem semantiku.
- Skrytyy #2: (Nadezhnost ↔ Follbek) pri otsutstvii pamyati vozvraschaem empty, no validnyy otvet.

ZEMNOY ABZATs:
One pole - three korziny istochnikov. Nikakikh padeniy na importe, nikakikh slozheniy None.
Request bezopasen dazhe bez BD/index.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from flask import Blueprint, jsonify, render_template, render_template_string, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("bridge_routes", __name__, url_prefix="/bridge")

def _safe_int(x: Any, d: int) -> int:
    try:
        return int(x)
    except Exception:
        return d

def _search_memory(q: str, topk: int) -> List[Dict[str, Any]]:
    try:
        from modules.memory.layers import search  # type: ignore
        items = search(q, top_k=topk) or []
        # Normalization to General View
        out = []
        for it in items:
            out.append({
                "kind": it.get("kind"),
                "text": it.get("text"),
                "score": it.get("score", 0.0),
                "id": it.get("id") or it.get("_id"),
            })
        return out
    except Exception:
        return []

def _search_global(q: str, topk: int) -> List[Dict[str, Any]]:
    # Place for extensions (external search/Internet disabled - fullback empty).
    return []

@bp.post("/query")
def query():
    d = request.get_json(force=True, silent=True) or {}
    q = str(d.get("q") or "").strip()
    if not q:
        return jsonify({"ok": True, "items": [], "sources": {"memory": 0, "global": 0}})
    topk = max(1, _safe_int(d.get("topk", 5), 5))
    mem = _search_memory(q, topk)
    glob = _search_global(q, topk)
    items = [{"source": "memory", **m} for m in mem] + [{"source": "global", **g} for g in glob]
    return jsonify({"ok": True, "items": items[:topk], "sources": {"memory": len(mem), "global": len(glob)}})

@bp.get("/admin")
def admin():
    try:
        return render_template("admin_bridge.html")
    except Exception:
        return render_template_string("""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Bridge - Ester</title>
<style>
body{font:14px/1.4 system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:24px}
.card{border:1px solid #ddd;border-radius:12px;padding:16px;max-width:960px}
input,button{padding:8px 10px;border-radius:10px;border:1px solid #ccc}
.row{display:flex;gap:8px;margin:10px 0}
pre{background:#fafafa;border:1px solid #eee;border-radius:8px;padding:12px;white-space:pre-wrap}
</style>
<div class="card">
  <h1>Bridge</h1>
  <div class="row">
    <input id="q" placeholder="vvedite zapros" style="flex:1">
    <button onclick="go()">Nayti</button>
  </div>
  <pre id="out">(poka empty)</pre>
</div>
<script>
async function go(){
  const q = document.getElementById('q').value;
  const r = await fetch('/bridge/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q,topk:5})});
  const j = await r.json();
  document.getElementById('out').textContent = JSON.stringify(j,null,2);
}
</script>""")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b