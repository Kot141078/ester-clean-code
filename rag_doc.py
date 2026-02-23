# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, threading
from typing import Dict, Tuple, Optional, Any, List
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("rag_doc", __name__)

class DocEngine:
    """Uluchshennyy dvizhok raboty s dokumentami Ester"""
    def __init__(self):
        self._lock = threading.Lock()
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _get_paths(self) -> List[str]:
        return [
            os.environ.get("ESTER_MEM_DOCS_PATH", ""),
            os.path.join(os.environ.get("ESTER_ROOT", ""), "memory", "docs.jsonl"),
            "memory/docs.jsonl"
        ]

    def load_if_needed(self):
        if self._loaded: return
        with self._lock:
            if self._loaded: return
            for p in self._get_paths():
                if p and os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            for line in f:
                                if not line.strip(): continue
                                data = json.loads(line)
                                # Indeksiruem i po ID, i po normalizovannomu puti
                                doc_id = data.get("id") or data.get("path")
                                if doc_id:
                                    self._docs[doc_id] = data
                                    self._docs[os.path.normpath(doc_id)] = data
                        self._loaded = True
                        break
                    except Exception as e:
                        print(f"Oshibka RAG: {e}")

    def get_smart_chunk(self, doc_id: str, start: int, size: int) -> Dict[str, Any]:
        doc = self._docs.get(doc_id) or self._docs.get(os.path.normpath(doc_id))
        if not doc:
            return {"ok": False, "error": "not_found"}

        text = doc.get("text", "")
        # Uluchshenie: pytaemsya ne rvat predlozhenie
        end = min(start + size, len(text))
        if end < len(text):
            next_space = text.find(' ', end)
            if next_space != -1 and next_space - end < 20:
                end = next_space

        return {
            "ok": True,
            "text": text[start:end],
            "meta": doc.get("meta", {}),
            "total_size": len(text),
            "has_more": end < len(text)
        }

engine = DocEngine()

@bp.get("/get")
def get_doc():
    engine.load_if_needed()
    doc_id = request.args.get("id", "")
    start = int(request.args.get("start", 0))
    size = int(request.args.get("max_chars", 2000)) # Po umolchaniyu 2k simvolov
    
    res = engine.get_smart_chunk(doc_id, start, size)
    return jsonify(res), 200 if res["ok"] else 404

@bp.get("/_diag/rag_doc/state")
def diag_state():
    engine.load_if_needed()
    return jsonify({
        "status": "active",
        "docs_in_memory": len(engine._docs) // 2, # Delim na 2 iz-za dubley putey
        "engine": "Ester_RAG_v2_PreVector"
    })