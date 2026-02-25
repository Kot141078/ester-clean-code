# -*- coding: utf-8 -*-
"""P2P Consensus - detsentralizovannoe soglasovanie faktov po golosam uzlov.

Mosty:
- Yavnyy: (P2P ↔ Doverie) — kazhdyy uzel podpisyvaet golos za/protiv, reshenie nakaplivaetsya v zhurnale.
- Skrytyy 1: (Kriptografiya ↔ Nablyudaemost) - HMAC-podpisi proveryayutsya i otrazhayutsya v verifikatsii.
- Skrytyy 2: (Memory ↔ Ispolnenie) - prinyatye fakty mozhno “podnimat” v doverii (integratsiya s TrustIndex).

Zemnoy abzats:
Eto kak “podnyat ruki” v komnate: kto “za”, kto “protiv”. Kogda ruk dostatochno - schitaem, chto fakt prinyat.
Bez interneta - rabotaem lokalno; podpis nuzhna, chtoby ruki byli “chestnymi”."""
from __future__ import annotations

import os, json, time, hmac, hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

from modules.meta.ab_warden import ab_switch
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
CONS_FILE = STATE_DIR / "p2p_consensus.json"

def _load() -> Dict[str, Any]:
    try:
        if CONS_FILE.exists():
            return json.loads(CONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"proposals": {}, "history": []}

def _save(d: Dict[str, Any]) -> None:
    try:
        CONS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _sig(payload: Dict[str, Any], secret: Optional[str]) -> str:
    if not secret:
        return ""
    msg = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def propose(pid: str, text: str, author: Optional[str] = None) -> Dict[str, Any]:
    """Create an offer with id=pid.
    Slot A - direct recording. Slot B - auto-vote for the author if there is a peer_id."""
    peer = os.getenv("P2P_PEER_ID", "local")
    with ab_switch("P2PCONS") as slot:
        db = _load()
        if pid in db["proposals"]:
            return {"ok": False, "error": "already_exists", "id": pid}
        db["proposals"][pid] = {"id": pid, "text": text.strip(), "author": author or peer, "votes": [], "state": "open", "ts": time.time()}
        if slot == "B":
            # avto-golos avtora «za»
            v = vote(pid, vote_value=1, peer_id=peer, attach=False)
            db = _load()  # already signed up
        _save(db)
        return {"ok": True, "id": pid, "slot": slot}

def vote(pid: str, vote_value: int, peer_id: Optional[str] = None, attach: bool = True) -> Dict[str, Any]:
    """Vote "for" (1) or "against" (-1).
    attach=False - internal call (do not return the entire load)."""
    peer = peer_id or os.getenv("P2P_PEER_ID", "local")
    val = 1 if int(vote_value) >= 1 else -1
    secret = os.getenv("P2P_CONSENSUS_SECRET")
    with ab_switch("P2PCONS") as slot:
        db = _load()
        p = db["proposals"].get(pid)
        if not p:
            return {"ok": False, "error": "not_found", "id": pid}
        pay = {"id": pid, "peer": peer, "val": val, "ts": time.time()}
        pay["sig"] = _sig(pay, secret)
        # replace the node's vote if it has already voted
        p["votes"] = [v for v in p["votes"] if v.get("peer") != peer]
        p["votes"].append(pay)
        db["history"].append({"op": "vote", **pay})
        # status update
        score = sum(v.get("val", 0) for v in p["votes"])
        quorum = int(os.getenv("P2P_MIN_QUORUM", "2") or "2")
        if abs(score) >= quorum:
            p["state"] = "accepted" if score > 0 else "rejected"
            p["closed_ts"] = time.time()
        _save(db)
        res = {"ok": True, "id": pid, "slot": slot, "score": score, "state": p["state"], "votes": len(p["votes"])}
        return res if attach else {"ok": True}

def get(pid: str) -> Dict[str, Any]:
    db = _load()
    if pid not in db["proposals"]:
        return {"ok": False, "error": "not_found", "id": pid}
    return {"ok": True, "proposal": db["proposals"][pid]}

def list_ids(limit: int = 100) -> Dict[str, Any]:
    db = _load()
    keys = list(db["proposals"].keys())[-limit:]
    return {"ok": True, "ids": keys, "count": len(db["proposals"])}

def verify(pid: str) -> Dict[str, Any]:
    db = _load()
    p = db["proposals"].get(pid)
    if not p:
        return {"ok": False, "error": "not_found", "id": pid}
    secret = os.getenv("P2P_CONSENSUS_SECRET")
    bad: List[int] = []
    if secret:
        for i, v in enumerate(p.get("votes", [])):
            want = _sig({"id": pid, "peer": v.get("peer"), "val": v.get("val"), "ts": v.get("ts")}, secret)
            if v.get("sig") and v.get("sig") != want:
                bad.append(i)
    return {"ok": True, "id": pid, "invalid_indexes": bad, "checked": len(p.get("votes") or [])}

# finalnaya stroka
# c=a+b