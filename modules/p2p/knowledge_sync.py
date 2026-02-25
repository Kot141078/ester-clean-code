# -*- coding: utf-8 -*-
"""P2P Knowledge Sync - CRDT LWW-Set + merkli-kheshi dlya obmena znaniyami mezhdu uzlami.

Mosty:
- Yavnyy: (P2P ↔ Memory) — LWW-nabor (last-write-wins) khranit elementy znaniy s versiyami i “myagkimi” tombstone.
- Skrytyy 1: (Doverie/Emotsii ↔ Import) — pri merzhe uchityvaem Trust/Emotion dlya prioriteta lokalnogo/udalennogo.
- Skrytyy 2: (KG/Ontologiya ↔ Normalizatsiya) - teksty normalizuyutsya cherez Ontology Cache i can linkovatsya k KG.

Zemnoy abzats:
This is “papka dlya obmena”: kazhdyy fayl imeet vremya poslednego izmeneniya. Esli prishla bolee svezhaya versiya - berem ee.
Chtoby bystro ponimat razlichiya mezhdu papkami, schitaem merkli-koren po soderzhimomu."""
from __future__ import annotations

import os, json, time, hashlib, hmac
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from modules.meta.ab_warden import ab_switch
from modules.semantics.ontology_cache import reconcile_text
from modules.memory.trust_index import get_item as trust_get
from modules.memory.emotion_tagging import get as emo_get
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
SYNC_FILE = STATE_DIR / "p2p_knowledge_lww.json"

def _load() -> Dict[str, Any]:
    try:
        if SYNC_FILE.exists():
            return json.loads(SYNC_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"items": {}, "history": []}  # id -> {"value":..., "ts":float, "tomb":bool, "author":str}

def _save(d: Dict[str, Any]) -> None:
    try:
        SYNC_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _sig(payload: Dict[str, Any], secret: Optional[str]) -> str:
    if not secret:
        return ""
    msg = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def _leaf_hash(k: str, rec: Dict[str, Any]) -> str:
    raw = json.dumps([k, rec.get("ts"), rec.get("tomb"), rec.get("value")], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _merkle_root(items: Dict[str, Any]) -> str:
    # listy
    hashes = [ _leaf_hash(k, v) for k, v in sorted(items.items(), key=lambda x: x[0]) ]
    if not hashes:
        return hashlib.sha256(b"empty").hexdigest()
    while len(hashes) > 1:
        nxt: List[str] = []
        it = iter(hashes)
        for a in it:
            b = next(it, a)
            nxt.append(hashlib.sha256((a+b).encode("utf-8")).hexdigest())
        hashes = nxt
    return hashes[0]

def summary(limit: int = 20) -> Dict[str, Any]:
    db = _load()
    items = db["items"]
    ids = list(sorted(items.keys()))[-limit:]
    return {"ok": True, "count": len(items), "root": _merkle_root(items), "tail_ids": ids}

def merge_items(incoming: List[Dict[str, Any]], author: Optional[str] = None) -> Dict[str, Any]:
    """Merzh vkhodyaschikh elementov formata {"id":..., "value":{...}, "ts":?, "tomb":?}.
    Esli ts ne zadan - stavim tekuschee vremya na vkhode.
    Slot B — podkruchivaet ts v polzu bolee doverennogo istochnika (esli eto *nash* id)."""
    with ab_switch("P2P_SYNC") as slot:
        db = _load()
        applied = 0
        for rec in incoming or []:
            try:
                rid = str(rec.get("id") or "").strip()
                if not rid:
                    continue
                tomb = bool(rec.get("tomb", False))
                ts = float(rec.get("ts") or time.time())
                val = rec.get("value") or {}
                # normalization of text fields
                if isinstance(val, dict) and "text" in val and isinstance(val["text"], str):
                    val["text"] = reconcile_text(val["text"]).get("normalized") or val["text"]
                # weight adjustment in B: if our local fact is very trusted / with high affect, we will slightly move the vehicle up
                if slot == "B":
                    trust = float((trust_get(rid).get("item") or {}).get("score", 0.0))
                    affect = float((emo_get(rid).get("item") or {}).get("affect", 0.0))
                    ts += max(0.0, min(2.0, 0.05 * (trust + affect)))
                local = db["items"].get(rid)
                if (not local) or float(ts) >= float(local.get("ts", 0.0)):
                    db["items"][rid] = {"value": val, "ts": float(ts), "tomb": tomb, "author": author or os.getenv("P2P_PEER_ID","local")}
                    applied += 1
            except Exception:
                continue
        db["history"].append({"ts": time.time(), "n": applied, "source": author or "remote"})
        _save(db)
        return {"ok": True, "applied": applied, "root": _merkle_root(db["items"]), "slot": slot}

def pull_since(root_hash: str, max_items: int = 200) -> Dict[str, Any]:
    """A simple “bullet”: if the root matches, it doesn’t give anything back; otherwise we give the tail of the last max_items records."""
    db = _load()
    cur_root = _merkle_root(db["items"])
    if root_hash and root_hash == cur_root:
        return {"ok": True, "up_to_date": True, "root": cur_root, "items": []}
    # khvost
    ids = list(sorted(db["items"].keys()))[-max_items:]
    items = [{"id": i, **db["items"][i]} for i in ids]
    return {"ok": True, "up_to_date": False, "root": cur_root, "items": items}

def push_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prinimaem bandl vida {"items":[...] ,"sig": "..."}; podpis optsionalna.
    """
    secret = os.getenv("P2P_SYNC_SECRET")
    want = _sig({"items": bundle.get("items", [])}, secret) if secret else ""
    if secret and bundle.get("sig") and bundle.get("sig") != want:
        return {"ok": False, "error": "bad_signature"}
    return merge_items(list(bundle.get("items") or []), author=bundle.get("author"))

# finalnaya stroka
# c=a+b