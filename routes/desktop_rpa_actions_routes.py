# -*- coding: utf-8 -*-
"""routes/desktop_rpa_actions_routes.py - “stsenarii deystviy” s profilem i dzhitterom.

Ruchka:
  POST /desktop/rpa/act {
    "profile":"human_fast",
    "steps":[
      {"type":"move","x":800,"y":600,"from": {"x":200,"y":200}},
      {"type":"click","x":800,"y":600},
      {"type":"type","text":"Hello"},
      {"type":"sleep","ms":250}
    ]
  }

Rules:
- move: plavno peremeschaet kursor (servernaya approksimatsiya → seriya click bez nazhatiya? net, ispolzuem tolko konechnyy click;
        dlya vidimogo "vedeniya" kursora na khoste nuzhny agentnye api peremescheniya. Zdes delaem tolko itogovyy klik s pauzami.)
- click: POST /desktop/rpa/click (s dzhitterom koordinat)
- type: POST /desktop/rpa/type (s limited TPS)
- sleep: lokalnaya pauza

MOSTY:
- Yavnyy: (Profile ↔ Deystvie) skorostnye limity i pauzy primenyayutsya k lyubomu naboru shagov.
- Skrytyy #1: (Infoteoriya ↔ Ekspluatatsiya) edinyy format stsenariev dlya “ucheby” i “igr”.
- Skrytyy #2: (Anatomiya ↔ OS) skorost i mikrodrozh imitiruyut realnoe vzaimodeystvie.

ZEMNOY ABZATs:
Daet Ester “polnyy kontrol” v cheloveko-ponyatnom tempe. Rabotaet oflayn cherez uzhe suschestvuyuschie ruchki.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List
import json, http.client, time, random

from modules.ops.gaming_profile import pace_constraints, apply_jitter
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_rpa_actions", __name__, url_prefix="/desktop/rpa")

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=4.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "ignore")
    conn.close()
    try:
        return json.loads(data)
    except Exception:
        return {"ok": False, "error": "bad_reply", "raw": data}

@bp.route("/act", methods=["POST"])
def act():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    profile = str(data.get("profile") or "human_norm")
    steps: List[Dict[str, Any]] = list(data.get("steps") or [])
    limits = pace_constraints(profile)
    jitter_px = int(limits["jitter_px"])
    delay_ms = int(limits["delay_ms"])
    tps = float(limits["tps"])
    # “gentle” spacing between characters
    per_char_ms = int(max(1.0/tps, 0.01)*1000)

    trace: List[Dict[str, Any]] = []
    for st in steps:
        t = (st.get("type") or "").lower()
        if t == "sleep":
            ms = int(st.get("ms", delay_ms))
            time.sleep(max(0.0, ms/1000.0))
            trace.append({"type":"sleep","ms":ms}); 
            continue
        if t == "click":
            x, y = int(st.get("x",0)), int(st.get("y",0))
            x, y = apply_jitter(x, y, jitter_px)
            res = _post("/desktop/rpa/click", {"x": x, "y": y})
            trace.append({"type":"click","at":[x,y],"res":res})
            time.sleep(max(0.0, delay_ms/1000.0 + random.randint(0, limits["jitter_ms"])/1000.0))
            continue
        if t == "type":
            text = str(st.get("text") or "")
            # character-by-character sending - through an already existing /type (acceptable as a solid input)
            # Here - as a solid block, but with an additional pause so as not to exceed the TPS.
            res = _post("/desktop/rpa/type", {"text": text})
            trace.append({"type":"type","len":len(text),"res":res})
            time.sleep(max(0.0, per_char_ms*max(1,len(text))/1000.0))
            continue
        if t == "move":
            # the server does not move the cursor without a click - leave it as a “preparatory pause”
            time.sleep(max(0.0, delay_ms/1000.0))
            trace.append({"type":"move","note":"no-op on server"})
            continue
        trace.append({"type":t,"error":"unknown"})
    return jsonify({"ok": True, "profile": profile, "trace": trace})


def register(app):
    app.register_blueprint(bp)
    return app