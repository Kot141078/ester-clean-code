# -*- coding: utf-8 -*-
"""modules/aid/emergency.py - stsenarii SOS/eskalatsii: 112/103, kontakty Papy, check-listy, bezopasnye adaptery vyzova.

Mosty:
- Yavnyy: (Operatsii ↔ Lyudi) formiruem poshagovyy plan: what skazat po telefonu, what uvedomit, what podgotovit.
- Skrytyy #1: (Kibernetika ↔ Kontrol) A/B-slot, “tabletka”, zapret realnykh vyzovov bez yavnogo flaga.
- Skrytyy #2: (Memory ↔ Prioritet) uchityvaem prioritet Papy, khranim zhurnaly dlya posleduyuschey refleksii.

Zemnoy abzats:
This is “papka na kholodilnike”: number 112, tekst soobscheniya, spisok deystviy i kontakt blizkogo - vse pod rukoy.

# c=a+b"""
from __future__ import annotations
import json, os, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AID_AB = (os.getenv("AID_AB","A") or "A").upper()
ALLOW_REAL = bool(int(os.getenv("AID_ALLOW_REAL_CALLS","0")))
TRUST_ADAP = bool(int(os.getenv("AID_TRUST_ADAPTERS","0")))
DEF_COUNTRY = os.getenv("AID_DEFAULT_COUNTRY","BE")

ROOT = "data/aid"
LOG = os.path.join(ROOT, "aid_log.jsonl")

EMERGENCY_NUMS = {
    # prostaya karta bez onlayna
    "BE": {"emergency":"112", "medical":"112", "note":"EU 112"},
    "RU": {"emergency":"112", "medical":"103", "note":"Russian Federation"},
    "EU": {"emergency":"112", "medical":"112", "note":"Evrosoyuz 112"},
    "DEFAULT": {"emergency":"112", "medical":"112", "note":"Po umolchaniyu 112"},
}

def _append(entry: Dict[str, Any]):
    os.makedirs(ROOT, exist_ok=True)
    entry["ts"] = int(time.time())
    with open(LOG,"a",encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _contacts_sorted() -> List[Dict[str,Any]]:
    from modules.aid.contacts import get_all  # type: ignore
    st = get_all()
    cs = st.get("contacts",[])
    return sorted(cs, key=lambda c: int(c.get("priority",5)))

def _papa_bias_weight(title: str) -> float:
    try:
        from modules.policy.papa_priority import weight_task  # type: ignore
        return float(weight_task(title))
    except Exception:
        return 1.0

def _country_block(country: str | None) -> Dict[str,str]:
    c = (country or DEF_COUNTRY or "DEFAULT").upper()
    return EMERGENCY_NUMS.get(c) or EMERGENCY_NUMS["DEFAULT"]

def _compose_message(situation: str) -> str:
    return f"Urgent help. Situation: ZZF0Z. Address/location: <specify>. Victim: Ovner, <ovner_birth_date>. Contacts: <specify>. Need medical help."

def plan_sos(situation: str, location_hint: str = "", country: str | None = None) -> Dict[str, Any]:
    nums = _country_block(country)
    contacts = _contacts_sorted()
    msg = _compose_message(situation)
    steps = [
        {"step":"call_emergency", "number": nums["medical"], "script": msg, "note": nums["note"]},
        {"step":"notify_contact", "who": "pervyy iz prioritetnykh", "channel": "phone/sms/telegram", "template": f"Dad needs help: ZZF0Z. Location: ZZF1ZZ"},
        {"step":"prepare_info", "list": ["adres", "kod domofona", "allergii/lekarstva", "dokumenty"], "note":"derzhat pod rukoy"},
    ]
    plan = {"ok": True, "country": country or DEF_COUNTRY, "emergency": nums, "steps": steps, "contacts": contacts[:5]}
    _append({"kind":"plan_sos", "plan": plan, "bias": _papa_bias_weight("sos papa")})
    return plan

def simulate(situation: str, level: str = "medium") -> Dict[str, Any]:
    pl = plan_sos(situation)
    _append({"kind":"simulate", "level": level})
    return {"ok": True, "plan": pl, "note":"simulation; no real calls were made"}

def trigger(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Ispolnit TOLKO bezopasnye chasti: zhurnal, podgotovka tekstov/shablonov.
    Realnyy zvonok/sms - tolko esli AID_ALLOW_REAL_CALLS=1 i TRUST_ADAPTERS=1 (i vse ravno luchshe rukami)."""
    if AID_AB == "B":
        return {"ok": True, "executed": [], "note":"A/B=B: planning only"}
    done: List[Dict[str,Any]] = []
    for st in (plan.get("steps") or []):
        if st.get("step") == "prepare_info":
            done.append({"step":"prepare_info","status":"ready","items":st.get("list")})
        elif st.get("step") in ("call_emergency","notify_contact"):
            # safe conclusion “what to do”; no real calls without explicit flags
            entry = {"step": st["step"], "do":"manual", "number": st.get("number"), "template": st.get("template"), "script": st.get("script")}
            if ALLOW_REAL and TRUST_ADAP:
                entry["adapter"] = "system://disabled_by_default"
            done.append(entry)
    _append({"kind":"trigger", "count": len(done)})
    return {"ok": True, "executed": done}
# c=a+b