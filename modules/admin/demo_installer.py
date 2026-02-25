# -*- coding: utf-8 -*-
"""modules/admin/demo_installer.py - odin klik, chtoby vklyuchit “rezhim demonstratsii”.

Delaet:
- Ustanavlivaet presety vorkflou/igrovykh profiley i miks.
- Vklyuchaet Content-Guard (min_fps, require_visible).
- Sozdaet prostoy pleylist vnimaniya “demo”.
- Optionalno zapuskaet missiyu/pleylist.

MOSTY:
- Yavnyy: (Podgotovka ↔ Pokaz) odna knopka sobiraet rabochuyu stsenu.
- Skrytyy #1: (Infoteoriya ↔ UX) determinirovannyy nabor deystviy snizhaet entropiyu startovoy sessii.
- Skrytyy #2: (Kibernetika ↔ Volya) Ester sama “rezhissiruet” demo posle tvoego soglasiya.

ZEMNOY ABZATs:
Tolko lokalnye REST-vyzovy i JSON-fayly. Nikakikh vneshnikh zavisimostey.

# c=a+b"""
from __future__ import annotations
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _post(path: str, payload: dict) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=20.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _get(path: str) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=20.0)
    conn.request("GET", path)
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def quick_install() -> dict:
    res = {}
    # presety vorkflou
    res["presets"] = _post("/presets/install_all", {})
    # igrovye profili
    for name in ["FPS_basic","RTS_basic","Editor_notepad"]:
        res[f"profile_{name}"] = _post("/games/profiles/install", {"name": name})
    # miks Notepad+FPS
    res["mix"] = _post("/profiles/mix/create", {"name":"mix_demo","layers":["Editor_notepad","FPS_basic"]})
    # Content-Guard
    res["guard"] = _post("/guard/set", {"min_fps": 20, "require_visible": True, "manual_pause": False})
    # attention playlist (short)
    playlist = {
      "name":"demo",
      "items":[
        {"kind":"arrow","from":[300,200],"to":[420,240],"label":"Shag 1","delay_ms":800},
        {"kind":"box","box":{"left":120,"top":160,"width":220,"height":80},"label":"Shag 2","delay_ms":800}
      ],
      "loop": False
    }
    res["playlist"] = _post("/playlist/run", {"spec": playlist, "peers": []})
    return {"ok": True, "result": res}

def play_notepad_intro() -> dict:
    _post("/missions/start", {"id": "notepad_intro"})
    s1 = _post("/missions/step", {"id": "notepad_intro", "index": 0})
    s2 = _post("/missions/step", {"id": "notepad_intro", "index": 1})
    return {"ok": True, "steps": [s1, s2]}

def export_current_guide() -> dict:
    # odin snimok ekrana + overlei ot missii/pleylista → v guide_export
    return _post("/guide/export/current", {"name": "guide_demo"})