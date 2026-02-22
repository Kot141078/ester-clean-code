# -*- coding: utf-8 -*-
"""
modules/kg/autolink.py - deterministic offline entity autolinker for KG.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from typing import Any, Dict, List

from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("KG_AUTOLINK_DB", "data/kg/autolink.json")
NER_MIN_LEN = int(os.getenv("NER_MIN_LEN", "3") or "3")
NER_KEYWORDS_STR = os.getenv("NER_KEYWORDS", "Python,Ester,DefaultCity,YouTube,Whisper,FFmpeg,Bloom")
NER_KEYWORDS = [k.strip() for k in NER_KEYWORDS_STR.split(",") if k.strip()]
PEERS_STR = os.getenv("PEERS", "")
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
MIN_COUNT = int(os.getenv("MIN_COUNT", "2") or "2")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
MONITOR_THRESHOLD = int(os.getenv("MONITOR_THRESHOLD", "20") or "20")

log = logging.getLogger(__name__)

_STATE: Dict[str, Any] = {
    "updated": 0,
    "nodes": {},
    "edges": [],
    "last_cleanup": int(time.time()),
}


def _ensure() -> None:
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        with open(DB, "w", encoding="utf-8") as f:
            json.dump({"nodes": {}, "edges": [], "updated": 0, "last_cleanup": int(time.time())}, f, ensure_ascii=False, indent=2)


def _merge_payload(payload: Dict[str, Any], sum_counts: bool = False) -> None:
    nodes = payload.get("nodes")
    if isinstance(nodes, dict):
        for nid, data in nodes.items():
            if not isinstance(data, dict):
                continue
            key = str(nid or "").strip().lower()
            if not key:
                continue
            cur = _STATE["nodes"].get(key)
            if cur is None:
                _STATE["nodes"][key] = {
                    "id": key,
                    "name": str(data.get("name") or key),
                    "t": int(data.get("t") or int(time.time())),
                    "count": int(data.get("count") or 1),
                }
            else:
                c0 = int(cur.get("count") or 0)
                c1 = int(data.get("count") or 0)
                cur["count"] = c0 + c1 if sum_counts else max(c0, c1)

    edges = payload.get("edges")
    if isinstance(edges, list):
        seen = {json.dumps(e, ensure_ascii=False, sort_keys=True) for e in _STATE["edges"] if isinstance(e, dict)}
        for e in edges:
            if not isinstance(e, dict):
                continue
            marker = json.dumps(e, ensure_ascii=False, sort_keys=True)
            if marker in seen:
                continue
            seen.add(marker)
            _STATE["edges"].append(e)

    _STATE["updated"] = int(max(int(_STATE.get("updated") or 0), int(payload.get("updated") or 0)))
    _STATE["last_cleanup"] = int(payload.get("last_cleanup") or _STATE.get("last_cleanup") or int(time.time()))


def _load() -> None:
    _ensure()
    if os.path.isfile(DB):
        try:
            with open(DB, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                _merge_payload(payload, sum_counts=False)
        except Exception:
            log.warning("autolink: local state load failed", exc_info=True)

    for peer in PEERS:
        try:
            req = urllib.request.Request(peer, method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if isinstance(payload, dict):
                _merge_payload(payload, sum_counts=True)
        except Exception:
            log.warning("autolink: peer sync pull failed for %s", peer)


def _save() -> None:
    _STATE["updated"] = int(time.time())
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(_STATE, f, ensure_ascii=False, indent=2)
    sync_with_peers()


def sync_with_peers() -> None:
    if not PEERS:
        return
    body = json.dumps(_STATE, ensure_ascii=False).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(peer, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            log.warning("autolink: peer sync push failed for %s", peer)


def receive_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    _load()
    if isinstance(payload, dict):
        _merge_payload(payload, sum_counts=True)
        _save()
    return {"ok": True, "updated": int(_STATE.get("updated") or 0)}


def _ner(text: str, mode: str = "simple") -> List[str]:
    source = str(text or "")
    if mode == "regex":
        pattern = os.getenv("NER_REGEX", r"\b[A-YaA-Z][a-yaa-zA-Z0-9\-]{2,}\b")
        tokens = re.findall(pattern, source)
    else:
        phrases = re.findall(r"\b[A-ZA-YaE][a-za-yae]+(?:\s+[A-ZA-YaE][a-za-yae]+)*\b", source)
        singles = re.findall(r"\b[A-YaA-Z][a-yaa-zA-Z0-9\-]{" + str(NER_MIN_LEN - 1) + r",}\b", source)
        tokens = phrases + singles
    key_pattern = "|".join(re.escape(k) for k in NER_KEYWORDS)
    keys = re.findall(r"\b(" + key_pattern + r")\b", source, re.I) if key_pattern else []
    out = sorted({t.strip().lower() for t in (tokens + keys) if len(t.strip()) >= NER_MIN_LEN})
    return out[:50]


def cron_cleanup() -> Dict[str, Any]:
    _load()
    now = int(time.time())
    removed: List[str] = []
    if now - int(_STATE.get("last_cleanup") or 0) >= 86400:
        for nid, data in list((_STATE.get("nodes") or {}).items()):
            age_days = (now - int(data.get("t") or now)) / 86400.0
            if int(data.get("count") or 0) < MIN_COUNT or age_days > CRON_MAX_AGE_DAYS:
                removed.append(nid)
        for nid in removed:
            (_STATE.get("nodes") or {}).pop(nid, None)
        _STATE["edges"] = [e for e in (_STATE.get("edges") or []) if str((e or {}).get("to") or "") not in removed]
        _STATE["last_cleanup"] = now
        _save()
    return {"ok": True, "cleanup_time": int(_STATE.get("last_cleanup") or now), "removed": len(removed)}


def config(min_len: int = None, keywords: List[str] = None, regex: str = None) -> Dict[str, Any]:
    _load()
    global NER_MIN_LEN
    global NER_KEYWORDS
    if min_len is not None:
        NER_MIN_LEN = max(2, int(min_len))
    if keywords is not None:
        NER_KEYWORDS = [str(x).strip() for x in keywords if str(x).strip()]
    if regex is not None:
        os.environ["NER_REGEX"] = str(regex)
    return {"ok": True, "min_len": NER_MIN_LEN, "keywords": list(NER_KEYWORDS), "regex": os.getenv("NER_REGEX")}


def _rag_target(label: str) -> str:
    slug = re.sub(r"[^a-z0-9_\-]+", "-", str(label).lower()).strip("-")
    return "rag://entity/" + (slug or "unknown")


def autolink(items: List[Dict[str, Any]], mode: str = "simple", link_to_rag: bool = False) -> Dict[str, Any]:
    _load()
    cron_cleanup()

    added_n = 0
    added_e = 0
    nodes_updated: Dict[str, int] = {}
    links: List[Dict[str, Any]] = []

    for it in items or []:
        doc_id = str((it or {}).get("id") or "doc")
        text = str((it or {}).get("text") or "")
        text_low = text.lower()
        ents = _ner(text, mode)
        for ent in ents:
            nid = ent.lower()
            if nid not in _STATE["nodes"]:
                _STATE["nodes"][nid] = {"id": nid, "name": ent, "t": int(time.time()), "count": 1}
                added_n += 1
            else:
                _STATE["nodes"][nid]["count"] = int(_STATE["nodes"][nid].get("count") or 0) + 1
            nodes_updated[nid] = int(_STATE["nodes"][nid].get("count") or 0)

            edge = {"from": doc_id, "to": nid, "kind": "mentions", "t": int(time.time())}
            if edge not in _STATE["edges"]:
                _STATE["edges"].append(edge)
                added_e += 1

            for m in re.finditer(re.escape(ent), text_low):
                links.append(
                    {
                        "doc_id": doc_id,
                        "span": [int(m.start()), int(m.end())],
                        "label": ent,
                        "target": f"kg://node/{nid}",
                    }
                )

    _save()

    if WEBHOOK_URL and added_n > MONITOR_THRESHOLD:
        try:
            alert = {"added_nodes": added_n, "added_edges": added_e, "timestamp": int(time.time())}
            body = json.dumps(alert, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            log.warning("autolink: webhook notify failed", exc_info=True)

    try:
        from modules.mem.passport import append as _pp

        _pp("kg_autolink", {"nodes": added_n, "edges": added_e, "updated_nodes": nodes_updated}, "kg://autolink")
    except Exception:
        log.warning("autolink: passport append failed", exc_info=True)

    rag_hints: List[Dict[str, Any]] = []
    if link_to_rag:
        for nid, count in sorted(nodes_updated.items(), key=lambda x: (-x[1], x[0])):
            rag_hints.append({"node": nid, "target": _rag_target(nid), "weight": int(count)})

    return {
        "ok": True,
        "added_nodes": int(added_n),
        "added_edges": int(added_e),
        "nodes": [{"name": k, "count": v} for k, v in sorted(nodes_updated.items(), key=lambda x: -x[1])],
        "links": links,
        "rag_hints": rag_hints,
    }


def state() -> Dict[str, Any]:
    _load()
    return {
        "ok": True,
        "nodes": dict(_STATE.get("nodes") or {}),
        "edges": list(_STATE.get("edges") or []),
        "ner_min_len": int(NER_MIN_LEN),
        "ner_keywords": list(NER_KEYWORDS),
        "last_cleanup": int(_STATE.get("last_cleanup") or 0),
        "peers": list(PEERS),
    }
