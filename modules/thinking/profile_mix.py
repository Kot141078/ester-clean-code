# -*- coding: utf-8 -*-
"""modules/thinking/profile_mix.py - “miksy” profiley: sloynaya kompozitsiya khotkeev.

Khranilische: data/desktop/profile_mixes.json
Structure:
{
  "mixes": { "mix_name": {"layers":["FPS_basic","Editor_notepad"]} },
  "bindings": [{"title":"Notepad","mix":"mix_name"}]
}

API:
- create_mix(name, layers:list[str])
- get_mix(name) -> {"layers":[...], "hotkeys":[...], "pace":"..."} # pace vychislyaetsya po dominiruyuschemu sloyu (pervomu)
- bind_mix(title, mix)
- apply_for_title(title) -> poslat khotkei aktivnomu oknu (cherez window_ops.send_hotkey)

MOSTY:
- Yavnyy: (Igrovye/rabochie rezhimy ↔ Kontrol) sloi khotkeev obedinyayutsya pod tekuschuyu zadachu.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) deduplikatsiya khotkeev i opredelennyy poryadok sloev.
- Skrytyy #2: (Kibernetika ↔ Volya) miks zadaet “rezhim motoriki” Ester.

ZEMNOY ABZATs:
Simple JSON. Sovmestimo s uzhe suschestvuyuschim slovarem profiley (`game_profiles.py`). No matter what.

# c=a+b"""
from __future__ import annotations
import os, json
from typing import Dict, Any, List, Optional
from modules.thinking.game_profiles import list_profiles, get_binding_for
from modules.ops.window_ops import focus_by_title, send_hotkey
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
PATH = os.path.join(ROOT, "data", "desktop")
FILE = os.path.join(PATH, "profile_mixes.json")

def _ensure():
    os.makedirs(PATH, exist_ok=True)
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"mixes": {}, "bindings": []}, f, ensure_ascii=False, indent=2)

def _load() -> Dict[str, Any]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(obj: Dict[str, Any]) -> None:
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def create_mix(name: str, layers: List[str]) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name or not layers:
        return {"ok": False, "error": "name_and_layers_required"}
    obj = _load()
    obj["mixes"][name] = {"layers": list(layers)}
    _save(obj)
    return {"ok": True, "name": name, "layers": list(layers)}

def get_mix(name: str) -> Dict[str, Any]:
    obj = _load()
    mx = obj.get("mixes", {}).get(name)
    if not mx:
        return {"ok": False, "error": "mix_not_found"}
    profs = list_profiles()
    hotkeys: List[str] = []
    for layer in mx.get("layers", []):
        spec = profs.get(layer)
        if not spec:
            continue
        for seq in spec.get("hotkeys", []):
            if seq not in hotkeys:
                hotkeys.append(seq)
    pace = None
    if mx.get("layers"):
        first = profs.get(mx["layers"][0], {})
        pace = first.get("pace", "human_norm")
    return {"ok": True, "name": name, "layers": mx.get("layers", []), "hotkeys": hotkeys, "pace": pace or "human_norm"}

def bind_mix(title: str, mix: str) -> Dict[str, Any]:
    obj = _load()
    if mix not in obj.get("mixes", {}):
        return {"ok": False, "error": "mix_not_found"}
    b = obj.get("bindings", [])
    b = [x for x in b if x.get("title","").lower()!=title.lower()] + [{"title": title, "mix": mix}]
    obj["bindings"] = b
    _save(obj)
    return {"ok": True, "bindings": b}

def get_binding_for_title(title: str) -> Optional[Dict[str, Any]]:
    obj = _load()
    for it in obj.get("bindings", []):
        if it.get("title","").lower() in (title or "").lower():
            return {"title": it["title"], "mix": it["mix"]}
    return None

def apply_for_title(title: str) -> Dict[str, Any]:
    # Priority: if there is a mix bind, apply it; otherwise fake to a regular profile from game_profiles.
    bm = get_binding_for_title(title)
    if bm:
        mx = get_mix(bm["mix"])
        if not mx.get("ok"):
            return {"ok": False, "error": "mix_invalid"}
        focus_by_title(bm["title"])
        sent = []
        for seq in mx.get("hotkeys", []):
            ok = send_hotkey(seq)
            sent.append({"seq": seq, "ok": bool(ok)})
        return {"ok": True, "mode": "mix", "title": bm["title"], "mix": bm["mix"], "sent": sent, "pace": mx.get("pace")}

    # false - regular profile (if previously linked via game_profiles)
    from modules.thinking.game_profiles import get_binding_for as gp_get
    b = gp_get(title or "")
    if b:
        focus_by_title(b["title"])
        sent = []
        for seq in b["spec"].get("hotkeys", []):
            ok = send_hotkey(seq); sent.append({"seq": seq, "ok": bool(ok)})
        return {"ok": True, "mode": "profile", "title": b["title"], "profile": b["profile"], "sent": sent, "pace": b["spec"].get("pace","human_norm")}
    return {"ok": False, "error": "no_binding"}