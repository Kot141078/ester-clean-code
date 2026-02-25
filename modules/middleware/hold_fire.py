# -*- coding: utf-8 -*-
"""middleware/hold_fire.py — HumanLoop++ “Bolshoy stop”: mgnovennaya myagkaya zamorozka opasnykh deystviy.

Mosty:
- Yavnyy: (Chelovek ↔ Sistema) odno deystvie - i uzel ukhodit v “hold”: vse ne-zhiznenno vazhnoe blokiruetsya do TTL.
- Skrytyy #1: (Kibernetika ↔ Kontrol) A/B-slot, allowlist routes, JSONL-zhurnal dlya audita.
- Skrytyy #2: (Bezopasnost ↔ Politika) sochetaetsya s cautious_freedom i ConsentOps: obschiy predokhranitel.

Zemnoy abzats:
This is “bolshoy krasnyy gribok”: esli chto-to poshlo ne tak - zhmem, vse opasnoe zamiraet, servisy ostayutsya dostupnymi.

# c=a+b"""
from __future__ import annotations
import json, os, time, re
from typing import Any, Dict
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_hold = Blueprint("hold_fire", __name__)

HOLD_AB = (os.getenv("HOLD_AB","A") or "A").upper()
STATE_PATH = "data/policy/hold_state.json"
LOG_PATH = "data/policy/hold_chain.jsonl"
ALLOW = [p.strip() for p in (os.getenv("HOLD_ALLOW","/healthz,/admin/.*,/ops/hold/.*,/policy/caution/.*").split(",")) if p.strip()]

def _state() -> Dict[str, Any]:
    try: return json.load(open(STATE_PATH,"r",encoding="utf-8"))
    except Exception: return {"hold": False, "until": 0}

def _save(st: Dict[str, Any]):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(st, open(STATE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _append(ev: Dict[str, Any]):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    ev["ts"] = int(time.time())
    with open(LOG_PATH,"a",encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")

def _allowed(path: str) -> bool:
    for pat in ALLOW:
        if re.match(pat, path): return True
    return False

def register(app):
    app.register_blueprint(bp_hold)

@bp_hold.before_app_request
def _guard():
    if HOLD_AB == "B": return None
    st = _state()
    now = int(time.time())
    if st.get("hold", False) and now <= int(st.get("until",0)):
        p = request.path or ""
        if _allowed(p): return None
        _append({"kind":"hold_block","path":p,"method":request.method})
        return jsonify({"ok": False, "error":"hold_fire", "detail":{"until": st.get("until",0)}}), 403
    return None

@bp_hold.route("/ops/hold/status", methods=["GET"])
def status():
    st = _state()
    return jsonify({"ok": True, **st, "allow": ALLOW, "ab": HOLD_AB})

@bp_hold.route("/ops/hold/set", methods=["POST"])
def set_hold():
    d = request.get_json(True, True) or {}
    hold = bool(d.get("hold", True))
    ttl = int(d.get("ttl_sec", 300))
    until = int(time.time()) + (ttl if hold else 0)
    st = {"hold": hold, "until": until}
    _save(st); _append({"kind":"hold_set", **st})
    return jsonify({"ok": True, **st})
# c=a+b