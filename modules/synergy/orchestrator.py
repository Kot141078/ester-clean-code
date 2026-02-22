# -*- coding: utf-8 -*-
"""
modules/synergy/orchestrator.py — Naznachenie roley i puls sinergii.

Mosty:
- (Yavnyy) Algoritm podbora (zhadnyy so shtrafami konfliktov) i uvedomleniya uchastnikov cherez /proactive/dispatch.
- (Skrytyy #1) Politiki bezopasnosti/nagruzki iz YAML (rabochie chasy, nesovmestimosti roley).
- (Skrytyy #2) Puls komandy: agregirovannyy «synergy score» dlya operatora.

Zemnoy abzats:
Sobiraet komandu iz lyudey i mashin pod zadachu. Otdaet prozrachnyy plan naznacheniya
i obektivnyy indikator «naskolko komanda sbalansirovana».

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any, List, Tuple
from modules.synergy.state_store import STORE
from modules.synergy.capability_infer import infer_capabilities, fit_roles
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml
except Exception:
    yaml = None

POL_PATH = os.getenv("SYNERGY_POLICIES_PATH", "config/synergy_policies.yaml")

DEFAULT_POL = {
    "max_roles_per_agent": 2,
    "incompat": [["operator","strategist"]],  # po umolchaniyu luchshe razdelyat
    "required_for_purpose": {
        "aerorazvedka": ["strategist","operator","platform"]
    }
}

def _load_policies() -> Dict[str, Any]:
    if not yaml or not os.path.exists(POL_PATH):
        return dict(DEFAULT_POL)
    try:
        return yaml.safe_load(open(POL_PATH,"r",encoding="utf-8")) or dict(DEFAULT_POL)
    except Exception:
        return dict(DEFAULT_POL)

def assign(team_name: str) -> Dict[str, Any]:
    team = STORE.get_team(team_name)
    if not team:
        return {"ok": False, "error": "team_not_found"}

    policies = _load_policies()
    roles_needed: List[str] = list(team.get("roles_needed", [])) or policies.get("required_for_purpose", {}).get(team.get("purpose",""), [])
    agents = STORE.list_agents()
    # Rasschet prigodnosti
    scores: Dict[str, Dict[str, float]] = {}
    for a in agents:
        caps = infer_capabilities(a)
        scores[a["id"]] = fit_roles(caps)

    assigned: Dict[str, str] = {}
    taken: Dict[str, int] = {}

    # Zhadnyy podbor po maksimalnomu score dlya kazhdoy roli
    for role in roles_needed:
        best_id, best_s = None, -1.0
        for a in agents:
            s = scores.get(a["id"], {}).get(role, 0.0)
            # shtraf za peregruz
            s -= 0.1 * taken.get(a["id"], 0)
            # nesovmestimosti
            for r_prev, aid in assigned.items():
                if aid == a["id"] and [r_prev, role] in policies.get("incompat", []):
                    s -= 0.2
            if s > best_s:
                best_id, best_s = a["id"], s
        if best_id:
            assigned[role] = best_id
            taken[best_id] = taken.get(best_id, 0) + 1
            STORE.assign_role(team_name, role, best_id)

    return {"ok": True, "team": team_name, "assigned": assigned, "scores": scores}

def synergy_pulse(team_name: str) -> Dict[str, Any]:
    team = STORE.get_team(team_name) or {}
    roles = team.get("roles_needed", [])
    assigned = team.get("assigned", {})
    if not roles:
        return {"ok": True, "team": team_name, "score": 0.0, "coverage": 0.0, "assigned": assigned}

    # Otsenka: pokrytie roley + sredniy score naznachennykh
    agents = {a["id"]: a for a in STORE.list_agents()}
    coverage = sum(1 for r in roles if r in assigned) / max(1, len(roles))
    comp = []
    for r, aid in assigned.items():
        a = agents.get(aid)
        if not a: continue
        s = fit_roles(infer_capabilities(a)).get(r, 0.0)
        comp.append(s)
    quality = sum(comp)/len(comp) if comp else 0.0
    score = round(0.6*coverage + 0.4*quality, 3)
    return {"ok": True, "team": team_name, "score": score, "coverage": coverage, "quality": quality, "assigned": assigned}

def notify_assignments(team_name: str, plan: Dict[str, str]) -> Dict[str, Any]:
    if os.getenv("SYNERGY_NOTIFY","0") != "1":
        return {"ok": True, "dry": True}

    # Otpravlyaem v kanaly cherez lokalnyy /proactive/dispatch
    import urllib.request
    payloads = []
    for role, aid in plan.items():
        agent = STORE.get_agent(aid) or {}
        ch = (agent.get("channels") or {})
        audience = "business"  # neytralnyy delovoy
        intent = "update"
        content = f"Naznachenie roli: {role} v komande {team_name}."
        body = {"audience": audience, "intent": intent, "content": content, "source_id": f"synergy:{team_name}:{role}:{aid}"}
        if "whatsapp" in ch:
            body["channel"] = "whatsapp"; body["to"] = ch["whatsapp"]
        elif "telegram" in ch:
            body["channel"] = "telegram"; body["to"] = ch["telegram"]
        else:
            # dat shans pravilu po umolchaniyu
            pass
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8080/proactive/dispatch", data=data, headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                payloads.append(resp.read().decode("utf-8","ignore"))
        except Exception as e:
            payloads.append(f"ERR:{e}")
    return {"ok": True, "results": payloads}