# -*- coding: utf-8 -*-
"""
modules/docs/env_index.py — Mini-doki ENV: svodka klyuchevykh peremennykh s opisaniem i tekuschimi znacheniyami.

Mosty:
- Yavnyy: (Dokumentatsiya ↔ Rantaym) edinoe mesto, gde vidno ENV i ikh smysl.
- Skrytyy #1: (Hub/Cron ↔ Operupravlenie) udobno proveryat konfig pered nochnymi zadachami.
- Skrytyy #2: (Survival/Bundle ↔ Perenosimost) to, chto ukhodit v bandly, zdes tozhe otrazheno.

Zemnoy abzats:
Eto kak list s nakleykami na servernoy stoyke: «chto za tumblery i kuda krutit».

# c=a+b
"""
from __future__ import annotations
import os, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Katalog izvestnykh ENV (opros uzhe vnedrennykh podsistem etoy sessii)
_CATALOG = [
    # Provenance
    ("PROV_ENABLE", "true|false", "Vklyuchit shtampovku profilea pamyati (provenance)"),
    ("PROV_DB", "path", "Fayl zhurnala provenance (JSONL)"),

    # Entity Linker
    ("ENTITY_LINK_LANG", "auto|ru|en|...", "Language dlya izvlecheniya suschnostey (optsionalno)"),

    # Hybrid RAG
    ("HYBRID_TOPK", "int", "Razmer vydachi gibridnogo retrivera"),

    # Ingest Guard
    ("INGEST_GUARD_DB", "path", "Fayl sostoyaniya kvot/istochnikov"),
    ("INGEST_TOKENS_PER_MIN", "int", "Tokenov v minutu na istochnik"),
    ("INGEST_BACKOFF_MS", "csv-ms", "Stupeni backoff pri 429/5xx"),

    # RBAC
    ("RBAC_MAP", "path", "Fayl roli/naznacheniya dlya JWT-RBAC"),

    # Discovery / Bootstrap
    ("DISCOVERY_AUTORUN", "true|false", "Fonovyy avto-skaner moduley"),
    ("DISCOVERY_INTERVAL_SEC", "int", "Period avtoskanera (sek)"),
    ("DISCOVERY_ROUTES_PKG", "pkg", "Paket, gde iskat Flask-routy"),
    ("DISCOVERY_ACTIONS_PKG", "pkg", "Paket, gde iskat eksheny «voli»"),

    # Cron / Backups
    ("CRON_AUTORUN", "true|false", "Vklyuchit nochnoy orkestrator"),
    ("CRON_TIME", "HH:MM", "Lokalnoe vremya ezhednevnogo progona"),
    ("CRON_TZ", "tz", "Chasovoy poyas (inform.)"),
    ("CRON_HEALTH_PATHS", "csv-paths", "Spisok health-ruchek dlya proverki"),
    ("CRON_REPORT_DIR", "path", "Katalog otchetov nochnogo progona"),
    ("CRON_RESPECT_GUARD", "true|false", "Drozhat pauzy mezhdu shagami"),

    ("BACKUP_DIR", "path", "Katalog bekapov (ZIP)"),
    ("BACKUP_KEEP", "int", "Skolko ZIP derzhat"),
    ("SNAPSHOT_DIRS", "csv-dirs", "Kakie katalogi arkhivirovat"),

    # Hub
    # (net yavnykh ENV)

    # P2P Bloom
    ("P2P_BLOOM_FILE", "path", "Fayl Bloom-filtra"),
    ("P2P_BLOOM_BITS", "int", "Razmer filtra v bitakh"),
    ("P2P_BLOOM_HASHES", "int", "Kolichestvo khesh-funktsiy"),
    ("P2P_BLOOM_SALT", "str", "Sol dlya stabilnykh pozitsiy"),
    ("P2P_GOSSIP_TIMEOUT", "int", "Taymaut HTTP pri sinkhronizatsii (sek)"),

    # Human Pill
    ("PILL_DB", "path", "Baza zayavok «pilyul»"),
    ("PILL_TTL_SEC", "int", "Vremya zhizni zayavki (sek)"),
    ("PILL_AUTO_DENY_EXP", "true|false", "Istekshie zayavki pomechat denied"),
    ("PILL_HEADER", "str", "Imya zagolovka podtverzhdeniya"),
    ("PILL_PATTERNS", "path", "Politika patternov (method+regex)"),

    # Survival Bundle
    ("SURVIVAL_OUT_DIR", "path", "Kuda skladyvat bandly"),
    ("SURVIVAL_INCLUDE", "csv-paths", "Chto vklyuchat v bandl"),
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