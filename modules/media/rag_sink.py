
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.media.rag_sink — optsionalnaya vstavka sobytiy mediapotoka v RAG‑indeks.
Mosty:
- Yavnyy: maybe_ingest_text(meta) — bezopasnyy vyzov iz watchers.process_file().
- Skrytyy #1: (ENV‑kontrol) — ESTER_RAG_INGEST=1 vklyuchaet rezhim, AB‑slot ESTER_RAG_INGEST_AB=B daet bystryy no‑op.
- Skrytyy #2: (Inzheneriya ↔ Prozrachnost) — vozvraschaet strukturu s id/ok, ne brosaet isklyucheniy.

Zemnoy abzats:
Eto «sinaps» mezhdu sensorami i pamyatyu: korotkaya duga, kotoraya dobavlyaet tekst pryamo v assotsiativnyy indeks.
# c=a+b
"""
import os
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ENABLED = os.getenv("ESTER_RAG_INGEST","0") in {"1","true","True"}
AB = os.getenv("ESTER_RAG_INGEST_AB","A").upper().strip() or "A"

def maybe_ingest_text(meta: Dict[str, Any]) -> Dict[str, Any]:
    if not ENABLED or AB == "B":
        return {"ok": True, "ingested": False, "reason": "disabled"}
    try:
        text = meta.get("preview") or meta.get("text") or ""
        if not text:
            return {"ok": True, "ingested": False, "reason": "no_text"}
        from modules.rag import hub
        resp = hub.add_text(text, {"src": meta.get("src",""), "kind": meta.get("kind","text")})
        return {"ok": True, "ingested": True, "id": resp.get("id")}
    except Exception as e:
        return {"ok": False, "ingested": False, "error": str(e)}