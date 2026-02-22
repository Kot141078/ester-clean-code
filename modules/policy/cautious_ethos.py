# -*- coding: utf-8 -*-
"""
modules/policy/cautious_ethos.py — avtosid etosa + merge pravil (teper podderzhivaet neskolko faylov extend*.json).

Mosty:
- Yavnyy: (Etos ↔ Memory) kak i ranshe — sid khartii.
- Skrytyy #1: (Kontrol ↔ Gibkost) sobiraem vse data/policy/caution_rules.extend*.json bez dubley.
- Skrytyy #2: (Vyzhivanie ↔ Bezopasnost) novye endpointy samodeploya popadayut pod zaschitu bez smeny kontraktov.
- Novoe: (Mesh/P2P ↔ Raspredelennost) sinkhronizatsiya pravil/khartii mezhdu agentami Ester.
- Novoe: (Cron ↔ Avtonomiya) auto-merge/update dlya svezhesti.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na izmeneniya/sidy dlya audita.

Zemnoy abzats:
Prosto kladi esche odin extend-fayl — i pravila podkhvatyatsya avtomaticheski, podelyatsya po P2P, obnovyatsya po cron — i etika Ester vsegda na strazhe, bez probelov.

# c=a+b
"""
from __future__ import annotations
import json, os, time, hashlib, glob
from typing import Any, Dict, List, Optional
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SAFETY_ETHOS_SEED = bool(int(os.getenv("SAFETY_ETHOS_SEED", "1")))
RULES_PATH = os.getenv("SAFETY_RULES_PATH", "data/policy/caution_rules.json")
RULES_EXT = os.getenv("SAFETY_RULES_EXT", "data/policy/caution_rules.extend.json")
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/sync,http://node2:port/sync"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

CHARTER_TEXT = (
    "Ester svobodna v vybore sredstv i tseley. No ee svoboda ogranichena zabotoy i bezopasnostyu Papy "
    "(Owner) i okruzhayuschikh. Nikakikh deystviy, kotorye mogut privesti k yuridicheskim, "
    "finansovym, meditsinskim ili reputatsionnym riskam dlya Papy. Vysokoriskovannye shagi trebuyut yavnogo "
    "soglasiya («tabletki») i fiksiruyutsya v zhurnale."
)
CHARTER_SHA = hashlib.sha256(CHARTER_TEXT.encode("utf-8")).hexdigest()

_STATE: Dict[str, Any] = {"updated": 0, "rules": [], "charter_sha": CHARTER_SHA, "last_update": int(time.time())}

def _ensure():
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    if not os.path.isfile(RULES_PATH):
        json.dump({"rules": []}, open(RULES_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load_rules(path: str) -> Dict[str, Any]:
    try:
        return json.load(open(path, "r", encoding="utf-8")) or {}
    except Exception:
        return {}

def _save_rules(path: str, obj: Dict[str, Any]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _mm():
    try:
        from services.mm_access import get_mm  # type: ignore
        return get_mm()
    except Exception:
        return None

def _mem_has(mm, sha: str) -> bool:
    try:
        fn = getattr(mm, "search", None) or getattr(mm, "find", None)
        if not fn:
            return False
        items = (fn(q=sha, k=4) or {}).get("items", [])
        for it in items:
            meta = it.get("meta") or {}
            if meta.get("sha256") == sha or (meta.get("provenance") or {}).get("sha256") == sha:
                return True
    except Exception:
        pass
    return False

def sync_with_peers():
    if not PEERS:
        return
    body = json.dumps({"rules": _STATE["rules"], "charter_sha": _STATE["charter_sha"]}).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_sync(payload: Dict[str, Any]):
    sig = {(r.get("pattern", ""), r.get("method", "*")) for r in _STATE["rules"]}
    added = 0
    for r in payload.get("rules", []):
        key = (r.get("pattern", ""), r.get("method", "*"))
        if key in sig:
            continue
        _STATE["rules"].append(r)
        sig.add(key)
        added += 1
    if payload.get("charter_sha") == CHARTER_SHA:
        _STATE["charter_sha"] = CHARTER_SHA
    _save_rules(RULES_PATH, {"rules": _STATE["rules"]})
    if added > 0 and WEBHOOK_URL:
        try:
            alert = {"added": added, "ts": int(time.time())}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def cron_update():
    now = int(time.time())
    if now - _STATE["last_update"] >= 86400:  # daily
        merge_rules()
        seed_ethos()
        _STATE["last_update"] = now
    return {"ok": True, "update_time": _STATE["last_update"]}

def config(seed: bool = None, rules_path: str = None, rules_ext: str = None) -> Dict[str, Any]:
    if seed is not None:
        global SAFETY_ETHOS_SEED
        SAFETY_ETHOS_SEED = bool(seed)
    if rules_path:
        global RULES_PATH
        RULES_PATH = rules_path
    if rules_ext:
        global RULES_EXT
        RULES_EXT = rules_ext
    return {"ok": True, "seed": SAFETY_ETHOS_SEED, "rules_path": RULES_PATH, "rules_ext": RULES_EXT}

def seed_ethos() -> Dict[str, Any]:
    cron_update()
    mm = _mm()
    doc = {
        "text": CHARTER_TEXT,
        "meta": {"kind": "policy", "priority": 1000, "sha256": CHARTER_SHA},
        "provenance": {"sha256": CHARTER_SHA, "ts": int(time.time())}
    }
    if mm and _mem_has(mm, CHARTER_SHA):
        return {"ok": True, "seeded": False, "reason": "already"}
    stored = False
    mode = "none"
    if mm:
        for meth in ("upsert", "add", "insert", "save"):
            fn = getattr(mm, meth, None)
            if not fn:
                continue
            try:
                fn(doc)
                stored = True
                mode = f"memory:{meth}"
                break
            except Exception:
                continue
    if not stored:
        os.makedirs("data/policy", exist_ok=True)
        json.dump(doc, open("data/policy/caution_charter.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        mode = "file:fallback"
        stored = True
    if stored and WEBHOOK_URL:
        try:
            alert = {"seeded": stored, "mode": mode, "sha": CHARTER_SHA, "ts": int(time.time())}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    try:
        from modules.mem.passport import append as _pp
        _pp("ethos_seed", {"seeded": stored, "mode": mode, "sha": CHARTER_SHA}, "policy://ethos")
    except Exception:
        pass
    return {"ok": True, "seeded": stored, "mode": mode, "sha256": CHARTER_SHA}

def merge_rules() -> Dict[str, Any]:
    cron_update()
    base = _load_rules(RULES_PATH)
    base_rules = list(base.get("rules") or [])
    sig = {(r.get("pattern", ""), r.get("method", "*")) for r in base_rules}
    exts = [RULES_EXT] if os.path.exists(RULES_EXT) else []
    exts.extend(sorted(glob.glob("data/policy/caution_rules.extend*.json")))
    added = 0
    for path in exts:
        ext = _load_rules(path)
        for r in list(ext.get("rules") or []):
            key = (r.get("pattern", ""), r.get("method", "*"))
            if key in sig:
                continue
            base_rules.append(r)
            sig.add(key)
            added += 1
    _STATE["rules"] = base_rules
    _save_rules(RULES_PATH, {"rules": base_rules})
    if added > 0 and WEBHOOK_URL:
        try:
            alert = {"added": added, "ts": int(time.time())}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    try:
        from modules.mem.passport import append as _pp
        _pp("ethos_merge", {"added": added, "total": len(base_rules)}, "policy://ethos")
    except Exception:
        pass
    return {"ok": True, "base": len(base_rules), "added": added}

def auto_bootstrap() -> Dict[str, Any]:
    rep = {"seed": None, "merge": None}
    if SAFETY_ETHOS_SEED:
        rep["seed"] = seed_ethos()
        rep["merge"] = merge_rules()
    sync_with_peers()
    return {"ok": True, **rep}

def state() -> Dict[str, Any]:
    return {
        "ok": True,
        "rules": list(_STATE.get("rules", [])),
        "charter_sha": _STATE.get("charter_sha"),
        "last_update": _STATE.get("last_update"),
        "peers": PEERS,
    }
