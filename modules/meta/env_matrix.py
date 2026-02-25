# -*- coding: utf-8 -*-
"""env_matrix.py - svodnaya matritsa ENV dlya Ester.

Mosty:
- Yavnyy: (Dokumentatsiya ↔ Rantaym) - vydaem polnyy perechen peremennykh okruzheniya, defolty i naznachenie.
- Skrytyy 1: (UX ↔ Podderzhka) — udobnyy spisok dlya proverok i instruktsiy admina.
- Skrytyy 2: (Nadezhnost ↔ A/B) — podcherkivaem peremennye dlya slotov i avtokatbeka.

Zemnoy abzats:
Edinyy slovar ENV: what est, zachem nuzhno, kakim po umolchaniyu. Udobno glyadet na /admin/docs."""
from __future__ import annotations
import os
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def env_matrix() -> Dict[str, Any]:
    defs = {
        "AB_MODE": ("A", "Globalnyy slot A/B po umolchaniyu"),
        "AB_AUTOROLLBACK": ("1", "Avto-otkat pri sboe v slote B"),
        "ESTER_STATE_DIR": ("~/.ester", "Katalog sostoyaniya"),
        "PHYSIO_AB": ("A", "Phosio/Signal slot"),
        "TRUST_AB": ("A", "Slot for Trust Index"),
        "BRANCH_AB": ("A", "Slot for Brancher"),
        "SEMANTICS_AB": ("A", "Slot for Kache Ontology"),
        "EMO_AB": ("A", "Slot for Emotion Tagging"),
        "P2PCONS_AB": ("A", "Slot for P2P Consensus"),
        "VIZ_AB": ("A", "Visualizer slot"),
        "KG_AB": ("A", "Slot for KG Bridge"),
        "BRIDGE_AB": ("A", "Slot dlya Personal↔Global Bridge"),
        "TIERS_AB": ("A", "Slot for Teers/Desai Memora"),
        "SENSORS_AB": ("A", "Slot for Sensors"),
        "TRUST_HMAC_SECRET": ("", "Secret for signing evidenka TrustIndex"),
        "P2P_CONSENSUS_SECRET": ("", "Secret for Consensus Votes Signatures"),
        "P2P_PEER_ID": ("local", "Identifikator tekuschego uzla"),
        "P2P_MIN_QUORUM": ("2", "Quorum of votes to make a decision"),
        "P2P_SYNC_AB": ("A", "Slot for Knowledge Sink"),
        "P2P_SYNC_SECRET": ("", "Sekret podpisi bandlov Sync"),
        "RUNTIME_WATCHDOG": ("1", "Enable watchdog upon registration"),
        "WATCHDOG_INTERVAL_SEC": ("10", "Interval heartbeat, sekund"),
    }
    out: Dict[str, Any] = {}
    for k, (default, desc) in defs.items():
        out[k] = {"value": os.getenv(k, default), "default": default, "desc": desc}
    return {"ok": True, "env": out}

# finalnaya stroka
# c=a+b