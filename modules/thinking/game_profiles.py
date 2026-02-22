# -*- coding: utf-8 -*-
"""
modules/thinking/game_profiles.py — profilnyy slovar igr/prilozheniy.

Soderzhimoe:
- Predustanovlennye profili: shablony khotkeev/deystviy, chastoty, bezopasnyy ritm.
- Privyazka profilya k oknu po chasti zagolovka (persist JSON).
- Poluchenie «aktivnogo profilya» po oknu.

Fayl-khranilische: data/desktop/game_profiles.json
Struktura:
{
  "bindings": [{"title":"Diablo","profile":"FPS_basic"}],
  "profiles": {
     "FPS_basic": { "hotkeys": ["CTRL+SHIFT+1","CTRL+SHIFT+2"], "pace": "human_fast", "notes": "..."},
     "RTS_basic": { ... }
  }
}

MOSTY:
- Yavnyy: (Igra ↔ Kontrol) gotovye raskladki i temp deystviy.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) standartizovannye «patterny klikov/klavish» umenshayut oshibku operatora.
- Skrytyy #2: (Kibernetika ↔ Volya) profil = «sostoyanie vnimaniya/motoriki» Ester.

ZEMNOY ABZATs:
Oflayn JSON. Privyazka po zagolovku okna bez SDK igr. Khotkei uvodyatsya cherez uzhe realizovannyy otpravitel.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
PATH = os.path.join(ROOT, "data", "desktop")
FILE = os.path.join(PATH, "game_profiles.json")

PRESETS: Dict[str, Dict[str, Any]] = {
    "FPS_basic": {
        "hotkeys": ["CTRL+SHIFT+1", "CTRL+SHIFT+2", "CTRL+SHIFT+3"],
        "pace": "human_fast",
        "notes": "Bystrye deystviya, korotkie pauzy, dlya dinamiki."
    },
    "RTS_basic": {
        "hotkeys": ["CTRL+1", "CTRL+2", "CTRL+3", "CTRL+S"],
        "pace": "human_norm",
        "notes": "Umerennyy temp, aktsent na khotkeyakh grupp."
    },
    "Editor_notepad": {
        "hotkeys": ["CTRL+S", "CTRL+N", "CTRL+O"],
        "pace": "human_slow",
        "notes": "Uchebnyy profil dlya Bloknota."
    }
}

def _ensure():
    os.makedirs(PATH, exist_ok=True)
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"bindings": [], "profiles": PRESETS}, f, ensure_ascii=False, indent=2)

def list_profiles() -> Dict[str, Any]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return obj.get("profiles", {})

def install_preset(name: str) -> Dict[str, Any]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if name not in PRESETS:
        return {"ok": False, "error": "unknown_preset"}
    obj.setdefault("profiles", {})[name] = PRESETS[name]
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return {"ok": True, "profile": name}

def bind_profile(title_part: str, profile: str) -> Dict[str, Any]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if profile not in obj.get("profiles", {}):
        return {"ok": False, "error": "profile_missing"}
    b = obj.get("bindings", [])
    b = [x for x in b if x.get("title","").lower()!=title_part.lower()] + [{"title": title_part, "profile": profile}]
    obj["bindings"] = b
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return {"ok": True, "bindings": b}

def get_binding_for(title: str) -> Optional[Dict[str, Any]]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        obj = json.load(f)
    for it in obj.get("bindings", []):
        if it.get("title","").lower() in title.lower():
            prof = obj.get("profiles", {}).get(it["profile"])
            if prof:
                return {"title": it["title"], "profile": it["profile"], "spec": prof}
    return None