# -*- coding: utf-8 -*-
"""modules/docs/env_index.py - Mini-doki ENV: svodka klyuchevykh peremennykh s opisaniem i tekuschimi znacheniyami.

Mosty:
- Yavnyy: (Dokumentatsiya ↔ Rantaym) edinoe mesto, where vidno ENV i ikh smysl.
- Skrytyy #1: (Hub/Cron ↔ Operupravlenie) udobno proveryat config pered nochnymi zadachami.
- Skrytyy #2: (Survival/Bundle ↔ Perenosimost) to, chto ukhodit v bandly, zdes tozhe otrazheno.

Zemnoy abzats:
Eto kak list s nakleykami na servernoy stoyke: “what za tumblery i kuda krutit.”

# c=a+b"""
from __future__ import annotations
import os, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Catalog of known ENVs (survey of already implemented subsystems of this session)
_CATALOG = [
    # Provenance
    ("PROV_ENABLE", "true|false", "Enable memory profile stamping (provenance)"),
    ("PROV_DB", "path", "Provenance log file (ZHSONL)"),

    # Entity Linker
    ("ENTITY_LINK_LANG", "auto|ru|en|...", "Language for entity extraction (optional)"),

    # Hybrid RAG
    ("HYBRID_TOPK", "int", "Hybrid Retriever Discharge Size"),

    # Ingest Guard
    ("INGEST_GUARD_DB", "path", "Quota/Source Status File"),
    ("INGEST_TOKENS_PER_MIN", "int", "Tokenov v minutu na istochnik"),
    ("INGEST_BACKOFF_MS", "csv-ms", "Stupeni backoff pri 429/5xx"),

    # RBAC
    ("RBAC_MAP", "path", "Role/assignment file for ZhVT-RVACH"),

    # Discovery / Bootstrap
    ("DISCOVERY_AUTORUN", "true|false", "Fonovyy avto-skaner moduley"),
    ("DISCOVERY_INTERVAL_SEC", "int", "Period avtoskanera (sek)"),
    ("DISCOVERY_ROUTES_PKG", "pkg", "Paket, gde iskat Flask-routy"),
    ("DISCOVERY_ACTIONS_PKG", "pkg", "Paket, gde iskat eksheny «voli»"),

    # Cron / Backups
    ("CRON_AUTORUN", "true|false", "Enable night orchestrator"),
    ("CRON_TIME", "HH:MM", "Local daily run time"),
    ("CRON_TZ", "tz", "Time zone (inform.)"),
    ("CRON_HEALTH_PATHS", "csv-paths", "List of health pens to check"),
    ("CRON_REPORT_DIR", "path", "Catalog of night run reports"),
    ("CRON_RESPECT_GUARD", "true|false", "Trembling pauses between steps"),

    ("BACKUP_DIR", "path", "Katalog bekapov (ZIP)"),
    ("BACKUP_KEEP", "int", "Skolko ZIP derzhat"),
    ("SNAPSHOT_DIRS", "csv-dirs", "Which directories to archive?"),

    # Hub
    # (no explicit ENV)

    # P2P Bloom
    ("P2P_BLOOM_FILE", "path", "Fayl Bloom-filtra"),
    ("P2P_BLOOM_BITS", "int", "Filter size in bits"),
    ("P2P_BLOOM_HASHES", "int", "Number of hash functions"),
    ("P2P_BLOOM_SALT", "str", "Salt for stable positions"),
    ("P2P_GOSSIP_TIMEOUT", "int", "Taymaut HTTP pri sinkhronizatsii (sek)"),

    # Human Pill
    ("PILL_DB", "path", "Database of \"pill\" requests"),
    ("PILL_TTL_SEC", "int", "Application lifetime (sec)"),
    ("PILL_AUTO_DENY_EXP", "true|false", "Expired applications should be marked as Denied"),
    ("PILL_HEADER", "str", "Acknowledgment header name"),
    ("PILL_PATTERNS", "path", "Politika patternov (method+regex)"),

    # Survival Bundle
    ("SURVIVAL_OUT_DIR", "path", "Kuda skladyvat bandly"),
    ("SURVIVAL_INCLUDE", "csv-paths", "What to include in the bundle"),
    ("SURVIVAL_ADD_LAST_BACKUP", "true|false", "Vkladyvat posledniy backup"),
    ("SURVIVAL_WEBSEEDS", "csv-urls", "Webseed'y (opts.)"),
    ("SURVIVAL_LABEL", "str", "Dop. metka imeni arkhiva"),
]

def _val(k: str)->str:
    return os.getenv(k, "")

def index()->Dict[str,Any]:
    items=[{"key":k,"type":t,"desc":d,"value":_val(k)} for (k,t,d) in _CATALOG]
    return {"ok": True, "generated": int(time.time()), "items": items}

# c=a+b