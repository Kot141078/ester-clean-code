# -*- coding: utf-8 -*-
from __future__ import annotations

"""people.py — kontaktnaya kniga Ester + utility.

Funktsii:
- upsert_person: sozdat/obnovit kontakt (chat_id, tz, interests, consent, mute, trust_level)
- log_message: pisat dialogi v state/dialog_<Imya>.jsonl (in|out, tekst, emotsii)
- read_transcript: chitat istoriyu
- mark_interaction: schetchiki chastoty soobscheniy (uslovnaya «nadoedlivost»)
- get_by_chat_id: obratnyy poisk

Fiks oshibki:
- expected an indented block after 'with' statement
  Prichina: v _write_link_file() posle `with open(...) as f:` ne bylo tela (json.dump byl zakommentirovan).

Usileniya:
- Ubrany krakozyabry v dokstringe (UTF‑8).
- Tipy sdelany sovmestimymi s Python 3.8+ (List[str], Optional[Dict[...]]) — menshe syurprizov na uzlakh.
- Zapis people.json teper atomic (cherez .tmp → replace), chtoby ne portit fayl pri vnezapnom stope.
- Nebolshaya validatsiya topics.

Mosty (trebovanie):
- Yavnyy most: people.json + tg_link_<user>.json → demony/integratsii (Telegram) poluchayut identichnost/kanal.
- Skrytye mosty:
  1) Infoteoriya ↔ ekspluatatsiya: nuisance_score = kompaktnyy signal nagruzki kanala (chastota vkhoda).
  2) Inzheneriya ↔ nadezhnost: atomarnaya zapis = predokhranitel ot chastichno zapisannykh JSON.

ZEMNOY ABZATs: v kontse fayla.
"""


import json
import os
import time
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = os.path.join("state")
os.makedirs(STATE_DIR, exist_ok=True)
PEOPLE_PATH = os.path.join(STATE_DIR, "people.json")

_DEFAULTS: Dict[str, Any] = {
    "lang": "ru",
    "tz": "UTC",
    "consent": False,
    "mute": False,
    "interests": [],
    "notes": "",
    "trust_level": 0.5,  # 0..1
    "last_seen_ts": 0.0,
    "msg_count_today": 0,
    "nuisance_score": 0.0,  # 0..1
}


def _load() -> Dict[str, Any]:
    if os.path.exists(PEOPLE_PATH):
        with open(PEOPLE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    return {}


def _save(data: Dict[str, Any]) -> None:
    # atomic write
    tmp = PEOPLE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PEOPLE_PATH)


def all_people() -> Dict[str, Any]:
    return _load()


def get_person(user: str) -> Optional[Dict[str, Any]]:
    return _load().get(user)


def get_by_chat_id(chat_id: int) -> Optional[str]:
    data = _load()
    for name, prof in data.items():
        try:
            if int((prof or {}).get("chat_id", 0)) == int(chat_id):
                return name
        except Exception:
            pass
    return None


def upsert_person(user: str, **patch: Any) -> Dict[str, Any]:
    data = _load()
    entry = data.get(user, {"user": user, **_DEFAULTS})
    entry.update({k: v for k, v in patch.items() if v is not None})
    entry["last_seen_ts"] = time.time()
    data[user] = entry
    _save(data)
    # sinkhronno — fayl tg_link_<Imya>.json dlya demonov
    if "chat_id" in entry and entry["chat_id"] is not None:
        _write_link_file(user, int(entry["chat_id"]))
    return entry


def set_consent(user: str, val: bool) -> Dict[str, Any]:
    return upsert_person(user, consent=bool(val))


def set_mute(user: str, val: bool) -> Dict[str, Any]:
    return upsert_person(user, mute=bool(val))


def set_topics(user: str, topics: List[str]) -> Dict[str, Any]:
    clean = [str(t).strip().lower() for t in (topics or []) if str(t).strip()]
    return upsert_person(user, interests=clean)


def mark_interaction(user: str, inbound: bool = True) -> Dict[str, Any]:
    data = _load()
    entry = data.get(user, {"user": user, **_DEFAULTS})
    entry["last_seen_ts"] = time.time()

    # obnovim dnevnoy schetchik i «nadoedlivost»
    entry["msg_count_today"] = int(entry.get("msg_count_today", 0)) + (1 if inbound else 0)
    # eksponentsialnyy raspad
    entry["nuisance_score"] = max(0.0, float(entry.get("nuisance_score", 0.0)) * 0.98)
    if inbound:
        entry["nuisance_score"] = min(1.0, float(entry["nuisance_score"]) + 0.03)

    data[user] = entry
    _save(data)
    return entry


def log_message(user: str, direction: str, text: str, emotions: Optional[Dict[str, float]] = None) -> None:
    path = os.path.join(STATE_DIR, f"dialog_{user}.jsonl")
    rec = {
        "ts": time.time(),
        "user": user,
        "direction": direction,  # "in" | "out"
        "text": text,
        "emotions": emotions or {},
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_transcript(user: str, limit: int = 200) -> List[Dict[str, Any]]:
    path = os.path.join(STATE_DIR, f"dialog_{user}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    out: List[Dict[str, Any]] = []
    for x in lines:
        try:
            out.append(json.loads(x))
        except Exception:
            pass
    return out


def _write_link_file(user: str, chat_id: int) -> None:
    path = os.path.join(STATE_DIR, f"tg_link_{user}.json")
    # FIX: telo bloka with
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"user": user, "chat_id": int(chat_id)}, f, ensure_ascii=False, indent=2)


__all__ = [
    "all_people",
    "get_person",
    "get_by_chat_id",
    "upsert_person",
    "set_consent",
    "set_mute",
    "set_topics",
    "mark_interaction",
    "log_message",
    "read_transcript",
]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Kontakty — kak kartochki patsientov v registrature: vazhno ne tolko imya, no i otmetki (soglasie, chasovoy poyas),
i istoriya vizitov (dialogi). Atomarnaya zapis — kak zakryt kartu na zaschelku: libo polnostyu obnovili zapis,
libo ostavili staruyu tseloy — bez poluotorvannykh stranits.
"""