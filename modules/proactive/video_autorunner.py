# -*- coding: utf-8 -*-
"""
modules/proactive/video_autorunner.py — proaktivnyy tsikl: podpiski (RSS/poisk/pryamye) → ingest_video → pamyat.

Funktsii:
  - run_once(mode="subs"|"search", topic=None, limit=None) -> dict: edinichnyy progon.
  - state() -> dict: kratkaya statistika (posledniy progon, skolko novykh).
  - register(app): registriruet blyuprint REST (sm. routes/proactive_video_routes.py).

ENV:
  - VIDEO_SUBS_ENABLED=0|1 — esli 1, razresheno ispolzovat iz planirovschika/kron.

Mosty:
- Yavnyy: (Memory ↔ Myshlenie) rezultat kladem v StructuredMemory/KG cherez ingest yadro — dostupno thinking_pipeline.
- Skrytyy #1: (Kibernetika ↔ Planirovschik) ogranichivaem limity/istochniki dlya ustoychivosti (norma reaktsii Ashbi).
- Skrytyy #2: (Inzheneriya ↔ Nadezhnost) sostoyanie sokhranyaetsya v data/video_subs_state.json dlya determinizma/dedupa.

Zemnoy abzats:
Eto "smennyy master": raz v iteratsiyu obkhodit truby (istochniki), otmechaet novye yaschiki (video), daet zadachu linii — raspilit/opisat.

# c=a+b
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Yadro ingest (drop-in)
try:
    from modules.ingest.video_ingest import ingest_video  # type: ignore
except Exception as e:
    ingest_video = None  # type: ignore

_CFG_PATH = os.path.join("config", "video_subscriptions.yaml")
_STATE_PATH = os.path.join("data", "video_subs_state.json")

def _persist_dir() -> str:
    root = os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(root, exist_ok=True)
    return root

def _load_yaml(path: str) -> Dict[str, Any]:
    # Mini-parser YAML dlya prostogo keysa (chtoby ne tyanut zavisimosti).
    # Podderzhivaem "subscriptions: - k:v ..." (kak v nashem fayle).
    data: Dict[str, Any] = {"subscriptions": []}
    if not os.path.isfile(path):
        return data
    cur: Optional[Dict[str, Any]] = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip() or raw.strip().startswith("#"):
                continue
            if raw.startswith("subscriptions:"):
                continue
            if raw.lstrip().startswith("- "):
                if cur:
                    data["subscriptions"].append(cur)
                cur = {}
                rest = raw.split("- ", 1)[1].strip()
                if rest:
                    # format "- key: value"
                    if ":" in rest:
                        k, v = rest.split(":", 1)
                        cur[k.strip()] = _parse_scalar(v.strip())
                continue
            if ":" in raw and cur is not None:
                k, v = raw.split(":", 1)
                cur[k.strip()] = _parse_scalar(v.strip())
    if cur:
        data["subscriptions"].append(cur)
    return data

def _parse_scalar(v: str) -> Any:
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.isdigit():
        try:
            return int(v)
        except Exception:
            return v
    if v.endswith("]") and "[" in v:
        # prosteyshiy spisok strok cherez zapyatuyu
        inner = v[v.find("[")+1:-1].strip()
        if not inner:
            return []
        parts = [x.strip().strip("'").strip('"') for x in inner.split(",")]
        return parts
    return v

def _load_state() -> Dict[str, Any]:
    if not os.path.isfile(_STATE_PATH):
        return {"last": 0, "seen": {}}
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last": 0, "seen": {}}

def _save_state(st: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

def _rss_fetch(url: str, timeout: float = 15.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

def _rss_parse_items(xml_text: str) -> List[Tuple[str, str]]:
    """
    Parsim RSS/Atom i vozvraschaem pary (id/url). Dlya YouTube Atom ispolzuem <yt:videoId> + <link>.
    """
    res: List[Tuple[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return res
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    # Atom entries
    for ent in root.findall(".//atom:entry", ns):
        vid = None
        e_yt = ent.find("yt:videoId", ns)
        if e_yt is not None and e_yt.text:
            vid = e_yt.text.strip()
        link = ""
        e_l = ent.find("atom:link", ns)
        if e_l is not None and e_l.attrib.get("href"):
            link = e_l.attrib["href"].strip()
        if vid and link:
            res.append((vid, link))
    # RSS fallback
    if not res:
        for it in root.findall(".//item"):
            guid = ""
            guid_el = it.find("guid")
            if guid_el is not None and guid_el.text:
                guid = guid_el.text.strip()
            lnk_el = it.find("link")
            link = (lnk_el.text or "").strip() if lnk_el is not None else ""
            if (guid or link) and link:
                res.append((guid or link, link))
    return res

def _ytsearch_to_url(query: str, limit: int = 3) -> List[str]:
    """
    Vozvraschaem spisok "virtualnykh" URL dlya yt-dlp: format ytsearchN:<query>
    (ingest_video prozrachno obrabatyvaet cherez yt-dlp).
    """
    n = max(1, min(int(limit or 3), 25))
    return [f"ytsearch{n}:{query}"]

def _should_enable() -> bool:
    v = (os.getenv("VIDEO_SUBS_ENABLED") or "0").strip()
    return v == "1"

def _ingest_url(url: str) -> Dict[str, Any]:
    if ingest_video is None:
        return {"ok": False, "error": "video_ingest core not available"}
    return ingest_video(src=url, want_meta=True, want_transcript=True, want_summary=True, prefer_audio=True, want_subs=True, chunk_ms=300_000)

def run_once(mode: str = "subs", topic: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Edinichnyy progon:
      - mode="subs": obkhodit config/video_subscriptions.yaml (enabled=1).
      - mode="search": vypolnyaet ytsearch po topic (obyazatelen).
    """
    st = _load_state()
    cfg = _load_yaml(_CFG_PATH)
    total, new_items, results = 0, 0, []
    now = int(time.time())

    if mode == "subs":
        subs: List[Dict[str, Any]] = [s for s in (cfg.get("subscriptions") or []) if int(s.get("enabled") or 0) == 1]
        for s in subs:
            sid = str(s.get("id") or "")
            kind = str(s.get("kind") or "rss")
            lim = int(s.get("limit") or (limit or 3))
            seen = set((st.get("seen") or {}).get(sid, []))
            urls: List[str] = []
            if kind == "rss":
                url = str(s.get("url") or "")
                if not url:
                    continue
                try:
                    xml = _rss_fetch(url)
                    items = _rss_parse_items(xml)
                    for iid, lnk in items[:lim]:
                        if iid not in seen:
                            urls.append(lnk)
                            seen.add(iid)
                except Exception:
                    continue
            elif kind == "direct":
                url = str(s.get("url") or "")
                if url:
                    urls.append(url)
            elif kind == "ytsearch":
                query = str(s.get("query") or "")
                if query:
                    urls.extend(_ytsearch_to_url(query, lim))
            # Progonim ingest
            for u in urls[:lim]:
                total += 1
                rep = _ingest_url(u)
                if rep.get("ok"):
                    new_items += 1
                results.append({"src": u, "rep": rep})
            # Obnovim seen
            st.setdefault("seen", {})[sid] = list(seen)
    elif mode == "search":
        if not topic:
            return {"ok": False, "error": "topic is required for mode=search"}
        urls = _ytsearch_to_url(topic, int(limit or 3))
        for u in urls:
            total += 1
            rep = _ingest_url(u)
            if rep.get("ok"):
                new_items += 1
            results.append({"src": u, "rep": rep})
    else:
        return {"ok": False, "error": f"unknown mode: {mode}"}

    st["last"] = now
    _save_state(st)
    return {"ok": True, "mode": mode, "topic": topic, "total": total, "new": new_items, "results": results, "ts": now}

def state() -> Dict[str, Any]:
    st = _load_state()
# return {"ok": True, "last": st.get("last", 0), "subscriptions": list((st.get("seen") or {}).keys())}