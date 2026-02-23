# -*- coding: utf-8 -*-
"""
tools/state_dump.py — svodka po faylam sostoyaniya v ESTER_STATE_DIR.

Mosty:
- Yavnyy: (QA ↔ Memory) — pokazyvaet razmery i metki vremeni klyuchevykh state-faylov.
- Skrytyy 1: (Diagnostika ↔ Infrastruktura) — pomogaet bystro ponyat, chto imenno pishet kazhdaya podsistema.
- Skrytyy 2: (Planirovanie ↔ Rezervnoe kopirovanie) — prigodno dlya prinyatiya resheniya o bekape.

Zemnoy abzats:
Skript probegaet po osnovnym faylam (kg, trust, emotion, p2p, heartbeat, tiers) i pechataet, chto est i skolko vesit.
"""
from __future__ import annotations
import os, json, time
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()

FILES = [
    "signals.json",
    "kg_store.json",
    "trust_index.json",
    "emotion_index.json",
    "p2p_consensus.json",
    "p2p_knowledge_lww.json",
    "heartbeat.json",
    "memory_tiers/short.jsonl",
    "memory_tiers/long.jsonl",
    "memory_tiers/archive.jsonl",
    "ontology.json",
    "ab_state.json",
]

def info(p: Path):
    if not p.exists():
        return {"path": str(p), "exists": False}
    st = p.stat()
    return {"path": str(p), "exists": True, "size": st.st_size, "mtime": st.st_mtime}

def main():
    print("ESTER_STATE_DIR =", STATE_DIR)
    out = [info(STATE_DIR / f) for f in FILES]
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

# finalnaya stroka
# c=a+b