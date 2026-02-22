# -*- coding: utf-8 -*-
"""
modules/mem/affect_priority.py — prioritezatsiya pamyati s uchetom affekta.

Mosty:
- Yavnyy: (Emotsii ↔ Vspominanie) vysokiy affekt podnimaet shans kratkoy refleksii i vsplytiya v otvetakh.
- Skrytyy #1: (Profile ↔ Prozrachnost) pishem svodku o raspredelenii affektov i otsechenii.
- Skrytyy #2: (RAG ↔ Kachestvo) top-zapisi mozhno dokleivat k prompt kak «kontekst nastroeniya».
- Novoe: (Mesh/P2P ↔ Raspredelennost) sinkhronizatsiya vesov affekta mezhdu agentami Ester.
- Novoe: (Cron ↔ Avtonomiya) avto-obnovlenie i chistka vesov dlya svezhesti.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na high-affekt sobytiya dlya audita.

Zemnoy abzats:
Eto kak «zakladka» na emotsionalno vazhnoy stranitse, no s setyu: takie mesta nakhodish bystree, delishsya po P2P, obnovlyaesh po cron — i pamyat Ester vsegda zhiva, bez zabytykh chuvstv.

# c=a+b
"""
from __future__ import annotations
import os, json, time, math, statistics
from typing import Any, Dict, List
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PATH = os.getenv("AFFECT_WEIGHTS", "data/mem/affect_weights.json")
W = float(os.getenv("AFFECT_W", "1.0") or "1.0")
DECAY_DAYS = float(os.getenv("DECAY_DAYS", "7.0") or "7.0")
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/sync,http://node2:port/sync"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
MIN_SEEN = int(os.getenv("MIN_SEEN", "2") or "2")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
MONITOR_AFF_THRESHOLD = float(os.getenv("MONITOR_AFF_THRESHOLD", "0.5") or "0.5")

state: Dict[str, Any] = {"updated": 0, "weights": {}, "last_update": int(time.time())}

def _ensure():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    if not os.path.isfile(PATH):
        json.dump({"weights": {}}, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load():
    global state
    _ensure()
    if os.path.isfile(PATH):
        try:
            loaded = json.load(open(PATH, "r", encoding="utf-8"))
            # merzhim weights (max weight)
            for key, data in loaded.get("weights", {}).items():
                if key in state["weights"]:
                    s = state["weights"][key]
                    s["w"] = max(s.get("w", 0), data.get("w", 0))
                    s["seen"] += data.get("seen", 0)
                else:
                    state["weights"][key] = data
            state["updated"] = loaded.get("updated", state["updated"])
            state["last_update"] = loaded.get("last_update", state["last_update"])
        except Exception:
            pass
    # Sinkh ot peers pri starte
    if PEERS:
        for peer in PEERS:
            try:
                req = urllib.request.Request(f"{peer}", method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    peer_state = json.loads(r.read().decode("utf-8"))
                    for key, data in peer_state.get("weights", {}).items():
                        if key in state["weights"]:
                            s = state["weights"][key]
                            s["w"] = max(s.get("w", 0), data.get("w", 0))
                            s["seen"] += data.get("seen", 0)
                        else:
                            state["weights"][key] = data
            except Exception:
                pass

def _save():
    state["updated"] = int(time.time())
    json.dump({"weights": state["weights"]}, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    sync_with_peers()

def sync_with_peers():
    if not PEERS:
        return
    body = json.dumps({"weights": state["weights"]}).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_sync(payload: Dict[str, Any]):
    _load()
    for key, data in payload.get("weights", {}).items():
        if key in state["weights"]:
            s = state["weights"][key]
            s["w"] = max(s.get("w", 0), data.get("w", 0))
            s["seen"] += data.get("seen", 0)
        else:
            state["weights"][key] = data
    _save()

def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))

def _score(item: Dict[str, Any], now: float) -> float:
    aff = max(0.0, min(1.0, float(item.get("affect", 0.0))))
    t = float(item.get("t", now))
    age = max(0.0, (now - t) / 86400.0)
    recency = math.exp(-age / DECAY_DAYS)
    base = float(item.get("base", 1.0))
    return base * (_sigmoid(aff * 2.0) * W + recency)

def cron_update():
    _load()
    now = int(time.time())
    if now - state["last_update"] >= 86400:  # daily
        reprioritize(100)  # auto-update
        # Chistka
        to_remove = []
        for key, data in state["weights"].items():
            age_days = (now - data.get("ts", now)) / 86400
            if age_days > CRON_MAX_AGE_DAYS or data.get("seen", 0) < MIN_SEEN:
                to_remove.append(key)
        for key in to_remove:
            del state["weights"][key]
        state["last_update"] = now
        _save()
    return {"ok": True, "update_time": state["last_update"], "removed": len(to_remove)}

def config(w: float = None, decay_days: float = None) -> Dict[str, Any]:
    _load()
    if w is not None:
        global W
        W = float(w)
    if decay_days is not None:
        global DECAY_DAYS
        DECAY_DAYS = float(decay_days)
    return {"ok": True, "w": W, "decay_days": DECAY_DAYS}

def prioritize(items: List[Dict[str, Any]], top_k: int = 20) -> Dict[str, Any]:
    cron_update()
    now = time.time()
    if items:
        # On-fly dlya spiska
        scored = [( _score(it, now), it) for it in items or []]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [dict(it[1], _score=round(it[0], 6)) for it in scored[:max(1, int(top_k))]]
    else:
        # Iz state weights
        scored = [(data["w"], {"id": key, "w": data["w"]}) for key, data in state["weights"].items()]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [it[1] for it in scored[:max(1, int(top_k))]]
    # Profile
    try:
        from modules.mem.passport import append as _pp
        affs = [float(x.get("affect", 0.0)) for x in items or []]
        mean_aff = statistics.mean(affs) if affs else 0.0
        _pp("affect_prioritize", {"n": len(items or []), "top": len(top), "aff_mean": mean_aff}, "mem://affect")
        if WEBHOOK_URL and mean_aff > MONITOR_AFF_THRESHOLD:
            try:
                alert = {"aff_mean": mean_aff, "top_k": top_k, "ts": int(now)}
                body = json.dumps(alert).encode("utf-8")
                req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
    except Exception:
        pass
    return {"ok": True, "items": top}

def reprioritize(top: int = 100) -> Dict[str, Any]:
    _load()
    cron_update()
    try:
        from services.mm_access import get_mm  # type: ignore
        mm = get_mm()
        recs = mm.list_recent(limit=top) or []  # predpolagaetsya metod
    except Exception:
        recs = []
    now = time.time()
    affs = []
    for r in recs:
        meta = r.get("meta") or {}
        aff = float(meta.get("affect_score", 0.0))
        affs.append(aff)
        ts = float(r.get("ts", now))
        recency = math.exp(-(now - ts) / (DECAY_DAYS * 86400))
        w = _sigmoid(aff * 2.0) * recency * W
        key = str(r.get("id") or r.get("sha", ""))
        if key in state["weights"]:
            state["weights"][key]["w"] = max(state["weights"][key]["w"], w)
            state["weights"][key]["seen"] += 1
        else:
            state["weights"][key] = {"w": w, "ts": int(now), "seen": 1}
    _save()
    # Profile
    try:
        from modules.mem.passport import append as _pp
        mean_aff = statistics.mean(affs) if affs else 0.0
        _pp("affect_reprioritize", {"n": len(recs), "aff_mean": mean_aff}, "mem://affect")
    except Exception:
        pass
    return {"ok": True, "count": len(recs)}

def state() -> Dict[str, Any]:
    _load()
# return {"ok": True, "weights": state.get("weights", {}), "w": W, "decay_days": DECAY_DAYS, "last_update": state["last_update"], "peers": PEERS}