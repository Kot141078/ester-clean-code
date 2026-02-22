# -*- coding: utf-8 -*-
"""
modules/resilience/health.py — bystryy samo-chek: fayly, importy, marshruty (best-effort).

Mosty:
- Yavnyy: (Inzheneriya ↔ Nadezhnost) daet binarnyy otvet «zdorovo/net» i spisok preduprezhdeniy.
- Skrytyy #1: (Samopoznanie ↔ Kontrol) ispolzuet inventar/graf importov iz Self-Awareness.
- Skrytyy #2: (Bezopasnost ↔ Trust) proveryaet nalichie imprinta/klyucha podpisi.

Zemnoy abzats:
Kak vrach na obkhode: schupaem osnovnye «pulsy» — fayly na meste, moduli importiruyutsya, politiki chitayutsya.
Obedineno iz dvukh versiy: dobavlena FS-touch proverka, logging dlya pamyati Ester, P2P-status dlya detsentralizatsii.

# c=a+b
"""
from __future__ import annotations
import os, json, importlib, time
import logging
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka logirovaniya dlya "pamyati" warn v Ester
logging.basicConfig(filename=os.getenv("RESILIENCE_LOG", "data/logs/resilience_health.log"), level=logging.WARNING,
                    format="%(asctime)s - %(levelname)s - %(message)s")

MAXF = int(os.getenv("HEALTH_MAX_FILES", "500") or "500")
TOUCH = os.getenv("HEALTH_TOUCH", "data/health/touch.txt")  # Iz py1 dlya FS-check

def _safe_import(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        return False

def check() -> Dict[str, Any]:
    ok = True; warn = []
    # 0) FS-touch: bazovaya proverka zapisi/chteniya (iz py1, kak "puls" Ester)
    try:
        os.makedirs(os.path.dirname(TOUCH), exist_ok=True)
        ts = int(time.time())
        with open(TOUCH, "w", encoding="utf-8") as f:
            f.write(str(ts))
        with open(TOUCH, "r", encoding="utf-8") as f:
            if int(f.read().strip()) != ts:
                raise ValueError("FS read mismatch")
    except Exception as e:
        ok = False; warn.append(f"fs_touch:fail={str(e)}")
        logging.warning(f"FS touch failed: {str(e)}")
    # 1) Imprint/klyuch
    try:
        from modules.self.imprint import status as imp_status  # type: ignore
        st = imp_status()
        if not st.get("exists"):
            ok = False; warn.append("imprint:missing")
    except Exception:
        warn.append("imprint:unavailable")
        logging.warning("Imprint unavailable")
    try:
        from modules.trust.sign import key_status  # type: ignore
        ks = key_status()
        if not ks.get("exists"): warn.append("trust:key_missing")
    except Exception:
        warn.append("trust:unavailable")
        logging.warning("Trust unavailable")
    # 2) Inventar i graf
    try:
        from modules.self.awareness import scan_inventory, build_graph  # type: ignore
        inv = scan_inventory(); g = build_graph()
        if inv.get("stat", {}).get("files", 0) == 0:
            ok = False; warn.append("inventory:empty")
        # Probuem importirovat do MAXF moduley iz grafa
        n = 0; bad = 0
        for node in g.get("nodes", [])[:MAXF]:
            if not _safe_import(node): bad += 1
            n += 1
        if bad > 0: warn.append(f"imports:fail={bad}/{n}")
    except Exception:
        ok = False; warn.append("awareness:unavailable")
        logging.warning("Awareness unavailable")
    # 3) Politika ostorozhnosti
    merged = os.getenv("APP_POLICY_MERGED", "data/policy/caution_rules.merged.json")
    try:
        json.load(open(merged, "r", encoding="utf-8"))
    except Exception:
        warn.append("policy:merged_missing")
        logging.warning("Policy merged missing")
    # 4) P2P-status (rasshirenie dlya detsentralizatsii Ester, best-effort)
    try:
        from modules.p2p.status import get_status  # type: ignore
        ps = get_status()
        if not ps.get("connected", False): warn.append("p2p:not_connected")
    except Exception:
        warn.append("p2p:unavailable")
        logging.warning("P2P unavailable")
    # Logiruem vse warn dlya pamyati
    if warn:
        logging.warning(f"Health check warn: {', '.join(warn)}")
# return {"ok": ok, "warn": warn, "ts": int(time.time()), "count_warn": len(warn)}
# Ideya rasshireniya: dlya integratsii s Judge — otprav warn v oblachnyy sintez dlya "remonta" (e.g., auto-repair importov).
# Realizuyu v module health_judge.py: check() + HTTP to Judge, esli skazhesh.