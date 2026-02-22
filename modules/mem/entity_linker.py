# -*- coding: utf-8 -*-
"""
modules/mem/entity_linker.py — legkiy izvlekatel suschnostey + best-effort privyazka k KG.

Mosty:
- Yavnyy: (Memory ↔ KG) iz teksta dostaem suschnosti i apsertim uzly/svyazi.
- Skrytyy #1: (Profile ↔ Audit) kazhdaya operatsiya fiksiruetsya v «profilenom stole».
- Skrytyy #2: (RAG ↔ Navigatsiya) razmetka suschnostey uluchshaet posleduyuschiy retriv.

Zemnoy abzats:
Kak bibliotekar: uvidel imena/adresa/ssylki — polozhil kartochki v katalog, svyazal mezhdu soboy.
Obedineno iz trekh versiy: rasshiren regex-okhvat, dobavleny stats, svyaz s hypothesis, logirovanie dlya pamyati Ester.

# c=a+b
"""
from __future__ import annotations
import os, re, json
import urllib.request, urllib.error
import logging
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka logirovaniya dlya "pamyati" oshibok v Ester
logging.basicConfig(filename=os.getenv("MEM_LOG", "data/logs/mem_entity.log"), level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

KG_SHADOW = os.getenv("KG_SHADOW_DB", "data/mem/kg_shadow.json")

_stats = {"runs": 0, "linked": 0}  # Iz py2 dlya prozrachnosti

def _ensure():
    os.makedirs(os.path.dirname(KG_SHADOW), exist_ok=True)
    if not os.path.isfile(KG_SHADOW):
        json.dump({"nodes": {}, "edges": []}, open(KG_SHADOW, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(KG_SHADOW, "r", encoding="utf-8"))
def _save(j): json.dump(j, open(KG_SHADOW, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

RX = {
    "URL": re.compile(r"https?://[^\s]+", re.I),  # Iz py/py2
    "EMAIL": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.I),  # Iz py/py2
    "HANDLE": re.compile(r"@\w{2,}"),  # Iz py
    "HASHTAG": re.compile(r"#\w{2,}"),  # Iz py
    "PERSON": re.compile(r"\b([A-ZA-YaE][a-za-yae]+(?:\s+[A-ZA-YaE][a-za-yae]+){0,3})\b"),  # Uluchshen iz py1/py2
    "ORG": re.compile(r"\b([A-ZA-YaE]{2,}[A-ZA-YaEa-za-yae0-9]+(?:\s+(?:Inc|LLC|Ltd|Studio|Labs))?)\b"),  # Iz py1
    "PLACE": re.compile(r"\b(Bryussel[yae]?|DefaultCity|Moskva|Paris|Berlin|New York)\b", re.IGNORECASE),  # Iz py1
    "TECH": re.compile(r"\b(ChromaDB|LanceDB|FAISS|LM\s*Studio|PyTorch|TensorFlow|RAG)\b", re.IGNORECASE)  # Iz py1
}

def extract_entities(text: str) -> List[Dict[str, str]]:
    s = text or ""
    out = []
    for kind, rx in RX.items():
        for m in rx.finditer(s):
            val = m.group(0).strip()
            # Filtratsiya, kak v py1/py2
            if kind in ["PERSON", "ORG", "PLACE", "TECH"] and len(val) < 3: continue
            out.append({"type": kind, "value": val})
    # Dedup, kak v py1/py
    uniq = []; seen = set()
    for e in out:
        k = (e["type"], e["value"])
        if k in seen: continue
        seen.add(k); uniq.append(e)
    return uniq

def _kg_upsert_node(label: str, value: str) -> str:
    """
    Best-effort: pytaemsya postuchatsya v lokalnye /mem/kg/upsert, inache — pishem v shadow-kg.
    Vozvraschaet node_id (lokalnyy).
    """
    node_id = f"{label}:{value}"
    try:
        body = json.dumps({"label": label, "value": value}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8000/mem/kg/upsert", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as r:
            rep = json.loads(r.read().decode("utf-8"))
            nid = (rep.get("node") or {}).get("id")
            if nid: return str(nid)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        logging.error(f"KG upsert failed for {label}:{value}: {str(e)}")
        pass
    # Fallback na shadow
    j = _load()
    j["nodes"][node_id] = {"label": label, "value": value}
    _save(j); return node_id

def _kg_link(a: str, rel: str, b: str) -> None:
    try:
        body = json.dumps({"from": a, "rel": rel, "to": b}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8000/mem/kg/link", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2): return
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        logging.error(f"KG link failed {a} -> {rel} -> {b}: {str(e)}")
        pass
    # Fallback na shadow
    j = _load(); j["edges"].append({"from": a, "rel": rel, "to": b}); _save(j)

def link_text(text: str, memory_id: str | None = None, upsert: bool = True) -> Dict[str, Any]:
    ents = extract_entities(text or "")
    mapped = []
    for e in ents:
        label = {"URL": "URL", "EMAIL": "EMAIL", "HANDLE": "HANDLE", "HASHTAG": "TAG",
                 "PERSON": "NAME", "ORG": "ORG", "PLACE": "PLACE", "TECH": "TECH"}.get(e["type"], "ENTITY")
        if upsert:
            nid = _kg_upsert_node(label, e["value"])
        else:
            nid = f"{label}:{e['value']}"  # Bez upsert, kak v py2
        mapped.append({"node": nid, "label": label, "value": e["value"]})
        if memory_id:
            _kg_link(memory_id, "MENTIONS", nid)
    _stats["runs"] += 1; _stats["linked"] += len(mapped)
    # Svyaz s hypothesis iz py2 (best-effort)
    try:
        linked = [{"id": memory_id or "", "nodes": mapped}]
        body = json.dumps({"links": linked}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8000/mem/hypothesis/link", data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        logging.error("Hypothesis link failed")
        pass
    # Profile (best-effort), kak v py/py1
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm(); upsert_with_passport(mm, "entity_link", {"count": len(mapped), "memory_id": memory_id}, source="mem://entity_linker")
    except Exception:
        pass
    return {"ok": True, "entities": mapped}

# Alias dlya sovmestimosti s py1
def autolink(items: List[Dict[str, Any]], tags: List[str] | None = None) -> Dict[str, Any]:
    linked = []
    for it in items or []:
        text = str(it.get("text", ""))
        mem_id = str(it.get("id", ""))
        res = link_text(text, mem_id)
        linked.append({"id": mem_id, "entities": res["entities"]})
    return {"ok": True, "items": linked}

def status() -> Dict[str, Any]:
    j = _load()
# return {"ok": True, "stats": dict(_stats), "nodes": len(j.get("nodes", {})), "edges": len(j.get("edges", []))}
    # Ideya rasshireniya: dlya P2P-sinkhronizatsii shadow — dobav funktsiyu sync_shadow(peers: List[str]):
    #   for peer in peers:
    #       try: req to peer/kg_shadow, merge nodes/edges, resolve conflicts by timestamp.
    #   Esli nuzhno, realizuyu v otdelnom module sync_shadow.py dlya detsentralizatsii Ester.