# -*- coding: utf-8 -*-
"""modules/policy/cautious_freedom.py - Politika “Svobodna, no ne navredi Pape”: risk-otsenka, pravila, “tabletka”, status.

Mosty:
- Yavnyy: (Etika ↔ Operatsii) deystviya propuskayutsya cherez risk-otsenku s pritselom na bezopasnost Papy.
- Skrytyy #1: (Kibernetika ↔ Kontrol) A/B-rezhim, “tabletka”, tsepochka sobytiy dlya audita.
- Skrytyy #2: (Memory/Prioritet ↔ Ekonomika/Kod) uchityvaem prioritet Papy i classy riska (finansy/kod/set/privatnost).

Zemnoy abzats:
This is “sovest i remen bezopasnosti”: mozhno ekhat bystro, no s remnem i ne narushaya - chtoby Papu ne posadili i ne podstavili.

# c=a+b"""
from __future__ import annotations
import json, os, time, re, hashlib
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("SAFETY_AB","A") or "A").upper()
ENABLED = bool(int(os.getenv("SAFETY_ENABLE","1")))
REQUIRE_PILL_FOR_HIGH = bool(int(os.getenv("SAFETY_REQUIRE_PILL_FOR_HIGH","1")))
RULES_PATH = os.getenv("SAFETY_RULES_PATH","data/policy/caution_rules.json")
CHAIN_PATH = os.getenv("SAFETY_CHAIN","data/policy/caution_chain.jsonl")
DEFAULT_COUNTRY = os.getenv("SAFETY_DEFAULT_COUNTRY","BE")

CHARTER_TEXT = (
    "Esther is free to choose her means and ends. But her freedom is limited by the care and safety of the Pope"
    "(Ovner) and those around him. No actions that could lead to legal,"
    "financial, medical or reputational risks for the Pope. High-risk steps require explicit"
    "consent (“pills”) and are recorded in a journal."
)

def _ensure_defaults():
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    if not os.path.isfile(RULES_PATH):
        rules = [
            # Finansy: krupnye traty → high
            {"pattern": r"^/economy/ledger/expense$", "method":"POST", "risk":"financial", "level":"high", "amount_field":"amount", "threshold":100.0, "requires_pill": True},
            {"pattern": r"^/agency/papa/support/execute$", "method":"POST", "risk":"financial", "level":"high", "requires_pill": True},
            # Samoizmenenie koda
            {"pattern": r"^/self/extensions/watch/approve$", "method":"POST", "risk":"code", "level":"high", "requires_pill": True},
            {"pattern": r"^/self/extensions/watch/scan$", "method":"POST", "risk":"code", "level":"medium", "requires_pill": False},
            # Set/rasprostranenie
            {"pattern": r"^/thinking/web_context/expand$", "method":"POST", "risk":"network", "level":"low", "requires_pill": False},
            {"pattern": r"^/p2p/.*", "method":".*", "risk":"network", "level":"medium", "requires_pill": False},
            # SOS - real calling is prohibited here, only plans/templates (real is enabled by separate PapaAid flags)
            {"pattern": r"^/aid/trigger$", "method":"POST", "risk":"life_safety", "level":"medium", "requires_pill": False}
        ]
        json.dump({"rules": rules}, open(RULES_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(CHAIN_PATH), exist_ok=True)
    if not os.path.isfile(CHAIN_PATH):
        open(CHAIN_PATH,"a",encoding="utf-8").close()

def _append_chain(event: Dict[str, Any]):
    _ensure_defaults()
    event["ts"] = int(time.time())
    raw = json.dumps(event, ensure_ascii=False, sort_keys=True)
    event["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with open(CHAIN_PATH,"a",encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def _load_rules() -> List[Dict[str,Any]]:
    _ensure_defaults()
    try:
        return (json.load(open(RULES_PATH,"r",encoding="utf-8")) or {}).get("rules",[])
    except Exception:
        return []

def _pill_state_path() -> str:
    return "data/policy/caution_pill.json"

def _pill_state() -> Dict[str, Any]:
    try:
        j = json.load(open(_pill_state_path(),"r",encoding="utf-8"))
    except Exception:
        j = {"armed": False, "until": 0}
    if j.get("armed") and int(time.time()) > int(j.get("until",0)):
        j = {"armed": False, "until": 0}
    return j

def pill_set(arm: bool, ttl_sec: int = 300) -> Dict[str, Any]:
    st = {"armed": bool(arm), "until": int(time.time()) + (max(30, int(ttl_sec)) if arm else 0)}
    os.makedirs(os.path.dirname(_pill_state_path()), exist_ok=True)
    json.dump(st, open(_pill_state_path(),"w",encoding="utf-8"))
    _append_chain({"kind":"pill", **st})
    return {"ok": True, **_pill_state()}

_STATE_PATH = "data/policy/caution_state.json"

def _load_state() -> Dict[str, Any]:
    try:
        return json.load(open(_STATE_PATH,"r",encoding="utf-8"))
    except Exception:
        return {"enabled": ENABLED, "risk_tolerance": 0.25, "ab": AB, "country": DEFAULT_COUNTRY}

def _save_state(st: Dict[str, Any]):
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    json.dump(st, open(_STATE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def status() -> Dict[str, Any]:
    st = _load_state()
    st["pill"] = _pill_state()
    st["rules_count"] = len(_load_rules())
    st["charter_sha256"] = hashlib.sha256(CHARTER_TEXT.encode("utf-8")).hexdigest()
    return {"ok": True, **st}

def set_state(enabled: Optional[bool] = None, risk_tolerance: Optional[float] = None) -> Dict[str, Any]:
    st = _load_state()
    if enabled is not None: st["enabled"] = bool(enabled)
    if risk_tolerance is not None: st["risk_tolerance"] = max(0.0, min(1.0, float(risk_tolerance)))
    _save_state(st); _append_chain({"kind":"set_state", **st})
    return {"ok": True, **status()}

def charter() -> Dict[str, Any]:
    return {"ok": True, "charter": CHARTER_TEXT, "sha256": hashlib.sha256(CHARTER_TEXT.encode("utf-8")).hexdigest()}

def evaluate(path: str, method: str, body: Dict[str,Any] | None) -> Dict[str, Any]:
    """Vozvraschaet solution: {"allow":bool,"reason":str,"level":"low|medium|high","requires_pill":bool}
    Logika:
      1) A/B=B → ne blokiruem, only log.
      2) enabled=0 → propuskaem.
      3) Ischem pravilo po path/method; esli est threshold summy - uchityvaem.
      4) Dlya level=high: esli REQUIRE_PILL_FOR_HIGH=1 i tabletka ne vooruzhena → deny."""
    _ensure_defaults()
    st = _load_state()
    rules = _load_rules()
    pill = _pill_state().get("armed", False)
    if AB == "B" or not st.get("enabled", True):
        return {"allow": True, "reason":"disabled_or_AB_B", "level":"low", "requires_pill": False}

    hit = None
    for r in rules:
        if r.get("method",".*") != ".*" and r.get("method") != method.upper():
            continue
        if re.match(r.get("pattern","^$"), path):
            hit = r; break

    if not hit:
        return {"allow": True, "reason":"no_rule", "level":"low", "requires_pill": False}

    level = hit.get("level","low")
    requires_pill = bool(hit.get("requires_pill", False))

    # denezhnyy porog
    if hit.get("amount_field"):
        fld = hit["amount_field"]
        try:
            amt = float((body or {}).get(fld, 0))
        except Exception:
            amt = 0.0
        thr = float(hit.get("threshold", 0))
        if amt >= thr:
            level = "high"
            requires_pill = True

    # itog
    if level == "high" and REQUIRE_PILL_FOR_HIGH and not pill:
        return {"allow": False, "reason":"high_without_pill", "level": level, "requires_pill": True}
    if requires_pill and not pill:
        return {"allow": False, "reason":"requires_pill", "level": level, "requires_pill": True}
    return {"allow": True, "reason":"ok", "level": level, "requires_pill": requires_pill}
# c=a+b