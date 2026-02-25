# -*- coding: utf-8 -*-
"""modules/synergy/capability_infer.py — Evristiki sposobnostey bez oprosov.

Mosty:
- (Yavnyy) Preobrazuet profil/bio/telemetriyu v vektor sposobnostey i prigodnost k rolyam.
- (Skrytyy #1) “Signaly iz konteksta”: klyuchevye slova v bio, domeny, vozrast/stazh, kanalnye metki.
- (Skrytyy #2) Devaysy: parametry drona (vremya poleta, peyload, zaderzhka) → rol platform.

Zemnoy abzats:
Pozvolyaet Ester vybirat “who za chto otvechaet”: strateg (opyt/taktika), operator (reaktsiya),
platforma (dron s podkhodyaschimi parametrami), nablyudatel (kommunikatsiya).

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import math
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _norm01(x: float, lo: float, hi: float) -> float:
    if hi <= lo: return 0.0
    v = (float(x) - lo) / (hi - lo)
    return max(0.0, min(1.0, v))

def infer_capabilities(agent: Dict[str, Any]) -> Dict[str, float]:
    kind = agent.get("kind")
    prof = agent.get("profile", {})
    bio  = (agent.get("bio") or "").lower()

    caps: Dict[str, float] = {}

    if kind == "human":
        age = float(prof.get("age", 35) or 35)
        exp = float(prof.get("exp_years", max(0, age-20)) or 0)
        domains = [d.lower() for d in (prof.get("domains") or [])]

        # Reaction is higher in young people: inverse function of age + presence of the control/drones domain
        caps["reaction"] = 0.6 * (1.0 - _norm01(age, 20, 60)) + 0.4 * (1.0 if ("upravlenie" in domains or "drony" in domains or "pilot" in bio) else 0.0)
        # Experience/strategy - based on length of service and the words “veteran/tactician/analyst”
        caps["strategy"] = 0.6 * _norm01(exp, 0, 30) + 0.4 * (1.0 if any(k in bio for k in ["veteran","taktika","strateg","analiz"]) else 0.0)
        # Communication - according to words and the presence of business domains
        caps["comms"] = 0.5 * (1.0 if any(k in bio for k in ["kommunik","svyaz","koordinats"]) else 0.0) + 0.5 * (1.0 if any(k in domains for k in ["biznes","svyaz","operator svyazi"]) else 0.0)
        # Domain expertise - easy assessment
        caps["domain_aero"] = 1.0 if any(k in domains for k in ["aerorazvedka","avia","uav","drony"]) else 0.0

    elif kind == "device":
        dev = prof.get("device")
        if dev == "drone":
            ft  = float(prof.get("flight_time_min", 0) or 0)
            pay = float(prof.get("payload_g", 0) or 0)
            lat = float(prof.get("latency_ms", 100) or 100)
            caps["platform"] = 0.6 * _norm01(ft, 10, 40) + 0.3 * _norm01(pay, 50, 800) + 0.1 * (1.0 - _norm01(lat, 20, 200))
        else:
            caps["platform"] = 0.3

    # Normirovka
    for k,v in list(caps.items()):
        caps[k] = max(0.0, min(1.0, float(v)))
    return caps

def fit_roles(caps: Dict[str, float]) -> Dict[str, float]:
    """Suitability score by role."""
    return {
        "operator": 0.7*caps.get("reaction",0) + 0.3*caps.get("domain_aero",0),
        "strategist": 0.8*caps.get("strategy",0) + 0.2*caps.get("domain_aero",0),
        "communicator": 1.0*caps.get("comms",0),
        "platform": caps.get("platform",0),
        "observer": 0.4*caps.get("comms",0) + 0.3*caps.get("domain_aero",0) + 0.3*max(caps.get("strategy",0), caps.get("reaction",0)),
    }