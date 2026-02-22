# -*- coding: utf-8 -*-
"""
modules/synergy/role_model.py — rasshirennaya model roley dlya sinergii.

MOSTY:
- (Yavnyy) Dobavlyaet roli: mentor (nastavnik), backup (dubler), qa (otsenschik kachestva).
- (Skrytyy #1) Sovmestim s fit_roles iz capability_infer: rasshirenie poverkh bazovykh metrik.
- (Skrytyy #2) Balans «opyt↔reaktsiya»: myagkie koeffitsienty, ne lomayut uzhe naznachennye roli.

ZEMNOY ABZATs:
Delaet komandy zhiznesposobnee: u operatora poyavlyaetsya nastavnik, u platformy — dubler,
a kachestvo proveryaet «vtorye glaza» (QA). Vse — bez izmeneniya starykh kontraktov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict
from modules.synergy.capability_infer import infer_capabilities, fit_roles
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def fit_roles_ext(agent: Dict[str, object]) -> Dict[str, float]:
    """
    Vozvraschaet score po rasshirennomu naboru roley.
    """
    base = fit_roles(infer_capabilities(agent))
    # Dopolnitelnye roli
    caps = infer_capabilities(agent)
    mentor = 0.7 * caps.get("strategy", 0.0) + 0.3 * (1.0 - caps.get("reaction", 0.0))
    backup = 0.4 * caps.get("reaction", 0.0) + 0.3 * caps.get("domain_aero", 0.0) + 0.3 * caps.get("comms", 0.0)
    qa = 0.6 * caps.get("strategy", 0.0) + 0.4 * caps.get("comms", 0.0)
    base.update({
        "mentor": mentor,
        "backup": backup,
        "qa": qa,
    })
    # Normiruem 0..1
    for k, v in list(base.items()):
        base[k] = max(0.0, min(1.0, float(v)))
    return base