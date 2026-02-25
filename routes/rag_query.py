# -*- coding: utf-8 -*-
"""routes/rag_query.py - endpoint RAG (coarse→fine) s keshem otvetov.

Added:
  • Lokalnyy kesh `AnswerCache` (klyuch - normalizovannyy zapros). Esli zapis svezhaya - otdaem mgnovenno.
  • TTL beretsya iz data/config.json → ANSWER_CACHE_TTL_HOURS (ili ENV).

Kontrakt bez lomki: k otvetu addavleny polya:
  "cached": true|false, "cache_ttl_h": <int>

# c=a+b"""
from __future__ import annotations

import json, os, time
from typing import Any, Dict
from flask import Blueprint, Response, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _persist_dir() -> str:
    return os.getenv("PERSIST_DIR") or os.getenv("DATA_DIR") or "./data"

def _make_indexer():
    try:
        from modules.hier_index import HierIndexer  # type: ignore
        return HierIndexer(persist_dir=_persist_dir())
    except Exception:
        return None

def _make_cache():
    try:
        from modules.answer_cache import AnswerCache  # type: ignore
        return AnswerCache(persist_dir=_persist_dir())
    except Exception:
        return None

rag_bp = Blueprint("rag_bp", __name__)

@rag_bp.route("/query", methods=["POST"])
def rag_query_post() -> Response:
    payload: Dict[str, Any] = {}
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        payload = {}
    q = (payload.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "empty query"}), 400

    topk_chapters = int(payload.get("topk_chapters") or 5)
    topk_chunks = int(payload.get("topk_chunks") or 5)

    cache = _make_cache()
    if cache:
        cached = cache.get(q)
        if cached is not None:
            # glue the service fields and return it
            cached_out = dict(cached)
            cached_out["ok"] = True
            cached_out["query"] = q
            cached_out["cached"] = True
            cached_out["cache_ttl_h"] = cache.ttl_h  # type: ignore[attr-defined]
            return jsonify(cached_out), 200

    hi = _make_indexer()
    if hi is None:
        return jsonify({"ok": False, "error": "hier_indexer_unavailable"}), 500

    t0 = time.time()
    coarse = hi.search_coarse(q, topk=max(1, topk_chapters))
    t1 = time.time()
    fine = hi.search_fine(q, coarse, topk=max(1, topk_chunks))
    t2 = time.time()
    resp = {
        "timings_ms": {
            "coarse": round(1000.0 * (t1 - t0), 2),
            "fine": round(1000.0 * (t2 - t1), 2),
            "total": round(1000.0 * (t2 - t0), 2),
        },
        "coarse": coarse,
        "fine": fine,
    }
    # save to cache
    if cache:
        try:
            cache.put(q, resp, meta={"route": "rag_query"})
        except Exception:
            pass
    resp_out = dict(resp)
    resp_out["ok"] = True
    resp_out["query"] = q
    resp_out["cached"] = False
    resp_out["cache_ttl_h"] = (cache.ttl_h if cache else None)  # type: ignore[attr-defined]
    return jsonify(resp_out), 200

@rag_bp.route("/query", methods=["GET"])
def rag_query_form() -> Response:
    # form from previous package - unchanged, omitted for brevity
    html = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>RAG (L1→L2)</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;max-width:960px;margin:40px auto;padding:0 16px;}
h1{font-size:20px;margin:0 0 12px} textarea{width:100%;height:80px} .btn{padding:8px 14px;border:1px solid #999;border-radius:8px;background:#f7f7f7;cursor:pointer}
pre{white-space:pre-wrap;background:#f4f4f4;padding:12px;border-radius:8px} .sec{margin-top:18px} .hit{margin:8px 0;padding:10px;border:1px solid #e1e1e1;border-radius:8px}
.title{font-weight:600} .score{opacity:.7}</style>
<h1>RAG (coarse → fine)</h1>
<form onsubmit="return false;">
<textarea id="q" placeholder="vvedite zapros..."></textarea><br><br>
<label>TopK glav: <input id="k1" type="number" value="5" min="1" max="20"></label>  
<label>TopK chankov: <input id="k2" type="number" value="5" min="1" max="50"></label>  
<button class="btn" onclick="go()">Iskat</button>
</form>
<div class="sec" id="out"></div>
<script>
async function go(){
  const q=document.getElementById('q').value;
  const k1=parseInt(document.getElementById('k1').value||'5');
  const k2=parseInt(document.getElementById('k2').value||'5');
  const res=await fetch('',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q, topk_chapters:k1, topk_chunks:k2})});
  const j=await res.json(); const out=document.getElementById('out');
  if(!j.ok){ out.innerHTML='<pre>'+JSON.stringify(j,null,2)+'</pre>'; return; }
  let h=''; h+='<div class="hit"><div class="title">timings</div><pre>'+JSON.stringify(j.timings_ms,null,2)+'</pre></div>';
  h+='<div class="hit"><div class="title">coarse (glavy)</div>';
  for(const c of j.coarse||[]){ h+='<div class="hit"><div class="title">'+(c.title||'')+'</div><div class="score">score='+(c.score||0).toFixed(4)+'</div><div><pre>'+String(c.preview||'').slice(0,240)+'</pre></div></div>'; }
  h+='</div>'; h+='<div class="hit"><div class="title">fine (tsitaty)</div>';
  for(const f of j.fine||[]){ h+='<div class="hit"><div class="score">score='+(f.score||0).toFixed(4)+'</div><div><pre>'+String(f.text||'').slice(0,800)+'</pre></div></div>'; }
  h+='<div class="hit"><div class="title">cache</div><pre>'+JSON.stringify({cached:j.cached, ttl_h:j.cache_ttl_h},null,2)+'</pre></div>';
  h+='</div>'; out.innerHTML=h;
}
</script></html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


def register(app):
    app.register_blueprint(rag_bp)
    return app