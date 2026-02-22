# -*- coding: utf-8 -*-
"""
modules/kg/linker.py — legkiy entity-linker: vydelyaet imenovannye suschnosti i sshivaet pamyat ↔ KG ↔ gipotezy.

Mosty:
- Yavnyy: (KG ↔ Memory) pri poyavlenii zapisi — izvlekaem suschnosti i apsertim uzly KG.
- Skrytyy #1: (Gipotezy ↔ Obyasnimost) zapisi poluchayut ssylki na KG-uzly dlya buduschego RAG.
- Skrytyy #2: (Infoteoriya ↔ Dedup) uzly pereispolzuyutsya po klyucham (normalizovannyy tekst).
- Novoe: (Mesh/P2P ↔ Raspredelennost) sinkhronizatsiya grafa mezhdu agentami Ester.
- Novoe: (Cron ↔ Avtonomiya) ochistka starykh/redkikh uzlov dlya svezhesti BZ.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na bolshie dobavleniya dlya audita.

Zemnoy abzats:
Avtomaticheskaya «skrepka» s setyu: gde vstrechaetsya «Ester» ili «IBAN» — tam uzly/svyazi v grafe, podelennye P2P, pochischennye po cron, i s alertami — chtoby pamyat Ester byla vechnoy i coherent.

# c=a+b
"""
from __future__ import annotations
import os, re, json, time
from typing import Any, Dict, List
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("KG_DB", "data/kg/graph.json")
AB = (os.getenv("KG_LINK_AB", "A") or "A").upper()
NER_MIN_LEN = int(os.getenv("NER_MIN_LEN", "2") or "2")
HINTS_GPE_STR = os.getenv("HINTS_GPE", "DefaultCity,Moscow,Berlin,Paris,Bruxelles,DefaultCity,Moskva,Parizh")
HINTS_ORG_STR = os.getenv("HINTS_ORG", "Bank,University,LLC,Inc,S.A.,NV,OOO,PAO")
HINTS_GPE = [h.strip() for h in HINTS_GPE_STR.split(",") if h.strip()]
HINTS_ORG = [h.strip() for h in HINTS_ORG_STR.split(",") if h.strip()]
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/sync,http://node2:port/sync"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
MIN_SEEN = int(os.getenv("MIN_SEEN", "2") or "2")  # dlya cleanup
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # URL dlya alertov
MONITOR_THRESHOLD = int(os.getenv("MONITOR_THRESHOLD", "10") or "10")  # porog dlya webhook

IBAN_RE = re.compile(r"\b([A-Z]{2}[0-9]{2}[A-Z0-9]{11,30})\b")
PERSON_RE = re.compile(r"\b([A-ZA-Ya][a-za-ya]+(?:\s+[A-ZA-Ya][a-za-ya]+){0,3})\b")
ENTITY_RE = re.compile(r"\b([A-ZA-Ya][a-za-ya]+(?:\s+[A-ZA-Ya][a-za-ya]+){0,2})\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
URL_RE = re.compile(r"https?://[^\s]+")

state: Dict[str, Any] = {"updated": 0, "nodes": {}, "edges": [], "last_cleanup": int(time.time())}

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"nodes": {}, "edges": []}, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load():
    global state
    _ensure()
    if os.path.isfile(DB):
        try:
            loaded = json.load(open(DB, "r", encoding="utf-8"))
            # merzhim nodes (max seen), edges (append unique)
            for nid, data in loaded.get("nodes", {}).items():
                if nid in state["nodes"]:
                    s = state["nodes"][nid]
                    s["seen"] = max(s.get("seen", 0), data.get("seen", 0))
                else:
                    state["nodes"][nid] = data
            state["edges"].extend([e for e in loaded.get("edges", []) if e not in state["edges"]])
            state["updated"] = loaded.get("updated", state["updated"])
            state["last_cleanup"] = loaded.get("last_cleanup", state["last_cleanup"])
        except Exception:
            pass
    # Sinkh ot peers pri starte
    if PEERS:
        for peer in PEERS:
            try:
                req = urllib.request.Request(f"{peer}", method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    peer_state = json.loads(r.read().decode("utf-8"))
                    for nid, data in peer_state.get("nodes", {}).items():
                        if nid in state["nodes"]:
                            s = state["nodes"][nid]
                            s["seen"] += data.get("seen", 0)  # sum dlya raspredelennosti
                        else:
                            state["nodes"][nid] = data
                    state["edges"].extend([e for e in peer_state.get("edges", []) if e not in state["edges"]])
            except Exception:
                pass

def _save():
    state["updated"] = int(time.time())
    json.dump(state, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    sync_with_peers()

def sync_with_peers():
    if not PEERS:
        return
    body = json.dumps(state).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_sync(payload: Dict[str, Any]):
    _load()
    for nid, data in payload.get("nodes", {}).items():
        if nid in state["nodes"]:
            s = state["nodes"][nid]
            s["seen"] += data.get("seen", 0)
        else:
            state["nodes"][nid] = data
    state["edges"].extend([e for e in payload.get("edges", []) if e not in state["edges"]])
    state["updated"] = max(state["updated"], payload.get("updated", 0))
    _save()

def _mm():
    try:
        from services.mm_access import get_mm  # type: ignore
        return get_mm()
    except Exception:
        return None

def _kg_upsert_mm(node: Dict[str, Any]) -> None:
    mm = _mm()
    if not mm:
        return
    upsert = getattr(mm, "upsert", None) or getattr(mm, "save", None)
    if not upsert:
        return
    doc = {"text": node.get("value", ""), "meta": {"kind": "kg_node", "key": node.get("key"), "ts": int(time.time()), "props": node}}
    try:
        upsert(doc)
    except Exception:
        pass

def extract(text: str, hint_lang: str | None = None) -> Dict[str, Any]:
    if not text:
        return {"ok": True, "entities": {}}
    ents = {"PERSON": [], "GPE": [], "ORG": [], "BANK": [], "NAME": [], "EMAIL": [], "URL": [], "place": [], "org": []}
    # BANK / IBAN
    for m in IBAN_RE.finditer(text):
        ents["BANK"].append(m.group(1))
    # PERSON / NAME (kombo)
    for m in PERSON_RE.finditer(text):
        s = m.group(1)
        if len(s.split()) >= 2 and len(s) <= 60:
            ents["PERSON"].append(s)
    for m in ENTITY_RE.finditer(text):
        token = m.group(1).strip()
        if len(token) < NER_MIN_LEN:
            continue
        if token.lower() in ("eto", "kak", "chto", "gde", "kogda"):
            continue
        if any(suf in token for suf in HINTS_ORG):
            ents["org"].append(token)
            ents["ORG"].append(token)
        elif any(w in token for w in HINTS_GPE):
            ents["place"].append(token)
            ents["GPE"].append(token)
        else:
            ents["NAME"].append(token)
            ents["PERSON"].append(token)
    # EMAIL / URL
    for m in EMAIL_RE.finditer(text):
        ents["EMAIL"].append(m.group(0))
    for m in URL_RE.finditer(text):
        ents["URL"].append(m.group(0))
    # dedup
    for k in list(ents.keys()):
        ents[k] = sorted(set([x.strip() for x in ents[k] if x and x.strip()]))
    return {"ok": True, "entities": {k: v for k, v in ents.items() if v}, "lang": hint_lang or "auto"}

def cron_cleanup():
    _load()
    now = int(time.time())
    if now - state["last_cleanup"] >= 86400:  # daily
        to_remove = []
        for nid, data in state["nodes"].items():
            age_days = (now - data.get("ts", now)) / 86400
            if data.get("seen", 0) < MIN_SEEN or age_days > CRON_MAX_AGE_DAYS:
                to_remove.append(nid)
        for nid in to_remove:
            del state["nodes"][nid]
        state["edges"] = [e for e in state["edges"] if e["to"] not in to_remove]
        state["last_cleanup"] = now
        _save()
    return {"ok": True, "cleanup_time": state["last_cleanup"], "removed": len(to_remove)}

def config(hints_gpe: List[str] = None, hints_org: List[str] = None, min_len: int = None) -> Dict[str, Any]:
    _load()
    if hints_gpe:
        global HINTS_GPE
        HINTS_GPE = hints_gpe
    if hints_org:
        global HINTS_ORG
        HINTS_ORG = hints_org
    if min_len:
        global NER_MIN_LEN
        NER_MIN_LEN = int(min_len)
    return {"ok": True, "hints_gpe": HINTS_GPE, "hints_org": HINTS_ORG, "min_len": NER_MIN_LEN}

def upsert_to_kg(entities: Dict[str, List[str]], source_id: str = "", sha: str = "") -> Dict[str, Any]:
    if not entities:
        return {"ok": True, "note": "empty"}
    _load()
    cron_cleanup()
    added = 0
    ts = int(time.time())
    for typ, vals in entities.items():
        for val in vals:
            nid = f"{typ}:{val.lower()}"
            if nid not in state["nodes"]:
                state["nodes"][nid] = {"type": typ, "value": val, "seen": 1, "ts": ts}
                added += 1
            else:
                state["nodes"][nid]["seen"] = state["nodes"][nid].get("seen", 0) + 1
            # Edge
            from_id = f"sha:{sha or source_id}"
            edge = {"from": from_id, "to": nid, "rel": "MENTIONS", "ts": ts}
            if edge not in state["edges"]:
                state["edges"].append(edge)
            # mm upsert best-effort
            _kg_upsert_mm({"key": nid, "value": val, "type": typ})
    _save()
    # Webhook esli mnogo
    if WEBHOOK_URL and added > MONITOR_THRESHOLD:
        try:
            alert = {"added": added, "source_id": source_id or sha, "timestamp": ts}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    # Passport esli est
    try:
        from modules.mem.passport import append as _pp
        _pp("kg_linker", {"added": added, "source": source_id or sha}, "kg://linker")
    except Exception:
        pass
    return {"ok": True, "added": added}

def run(limit: int = 50) -> Dict[str, Any]:
    mm = _mm()
    if not mm:
        return {"ok": False, "error": "memory_unavailable"}
    search = getattr(mm, "search", None) or getattr(mm, "find", None)
    if not search:
        return {"ok": False, "error": "memory_ops_missing"}
    items = (search(q="*", k=limit) or {}).get("items", [])
    linked = 0
    preview = []
    for it in items:
        text = (it.get("text") or it.get("content") or "")[:20000]
        ext_res = extract(text)
        ents = ext_res.get("entities", {})
        if not ents:
            continue
        source_id = str(it.get("id", ""))
        sha = it.get("sha", "")
        upsert_res = upsert_to_kg(ents, source_id, sha)
        added = upsert_res.get("added", 0)
        if added > 0:
            linked += 1
        if AB == "A":
            meta = dict(it.get("meta") or {})
            meta["kg_keys"] = sorted(list(set([f"{typ}:{v.lower()}" for typ, vals in ents.items() for v in vals])))
            try:
                upsert = getattr(mm, "upsert", None) or getattr(mm, "save", None)
                if upsert:
                    it2 = dict(it)
                    it2["meta"] = meta
                    upsert(it2)
            except Exception:
                pass
        preview.append({"id": source_id, "kg": list(set([f"{typ}:{v.lower()}" for typ, vals in ents.items() for v in vals]))})
    return {"ok": True, "matched": len(items), "linked": linked, "ab": AB, "preview": preview[:10]}

def stats() -> Dict[str, Any]:
    _load()
    return {"ok": True, "nodes": len(state.get("nodes", {})), "edges": len(state.get("edges", []))}

def state() -> Dict[str, Any]:
    _load()
# return {"ok": True, "nodes": state.get("nodes", {}), "edges": state.get("edges", []), "hints_gpe": HINTS_GPE, "hints_org": HINTS_ORG, "last_cleanup": state["last_cleanup"], "peers": PEERS}