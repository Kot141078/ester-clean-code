# -*- coding: utf-8 -*-
"""
modules/video/index/auto_chapters.py — avto-detektor glav (chapters) po dampu video i subtitram.

Funktsii:
  • build_chapters(dump_path:str, force:bool=False) -> dict
     - Esli v dump.meta.yt_dlp.chapters uzhe est glavy — normalizuem i sokhranyaem.
     - Inache stroim evristicheski po taymkodam/punktuatsii/pauzam i dline teksta.
  • chapters_path(dump_path) -> str  # put k keshu glav: data/video_ingest/index/<dump_id>.chapters.json

Format glav (JSON):
  [{"title":"...", "start":<sec>, "end":<sec>, "snippet":"..."}, ...]

Mosty:
- Yavnyy: (Video ↔ Poisk) glavy — eto semanticheskie «oglavleniya», uskoryayuschie navigatsiyu i QA.
- Skrytyy #1: (Infoteoriya ↔ Inzheneriya) pereispolzuem bogatuyu metu yt-dlp pri nalichii, inache stroim ustoychivo ot subtitrov.
- Skrytyy #2: (Kibernetika ↔ Volya) pravila myshleniya mogut zapuskat avto-indeksatsiyu glav po raspisaniyu.

Zemnoy abzats:
Eto «oglavlenie k filmu»: delim rolik na glavy, kazhdoy daem chitaemoe imya i koordinaty vremeni — kak zakladki v knige.

# c=a+b
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")
INDEX_DIR = os.path.join(DATA_DIR, "index")
os.makedirs(INDEX_DIR, exist_ok=True)

_STATE = os.path.join(INDEX_DIR, "state.json")

_TS_VTT = re.compile(r"\[\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]\]")
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?\…])\s+")

def chapters_path(dump_path: str) -> str:
    dump_id = os.path.splitext(os.path.basename(dump_path))[0]
    return os.path.join(INDEX_DIR, f"{dump_id}.chapters.json")

def _load_dump(path: str) -> Dict[str, Any]:
    return json.load(open(path, "r", encoding="utf-8"))

def _hms_to_sec(hms: str) -> float:
    hh, mm, ss = hms.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)

def _iter_spans(text: str) -> List[Tuple[float, float, str]]:
    rows: List[Tuple[float, float, str]] = []
    if not (text or "").strip():
        return rows
    for line in text.splitlines():
        m = _TS_VTT.search(line)
        t = re.sub(_TS_VTT, "", line).strip()
        if m and t:
            s = _hms_to_sec(m.group(1)); e = _hms_to_sec(m.group(2))
            rows.append((s, e, t))
    if not rows:
        # bez taymkodov — odna ogromnaya «glava», no dlya UX sdelaem 5-min okna
        chunk = 300.0
        text = (text or "").strip()
        parts = _SENT_SPLIT.split(text)
        acc = []; s = 0.0
        for i, sent in enumerate(parts):
            acc.append(sent.strip())
            if len(" ".join(acc)) > 900 or i % 12 == 0:
                rows.append((s, s + chunk, " ".join(acc)))
                s += chunk; acc = []
        if acc:
            rows.append((s, s + chunk, " ".join(acc)))
    return rows

def _title_from_text(t: str, max_words: int = 8) -> str:
    clean = re.sub(r"[\[\]\(\)<>{}#*_]+", "", t).strip()
    words = re.findall(r"[A-Za-zA-Yaa-ya0-9\-]+", clean)
    return " ".join(words[:max_words]) or "Glava"

def _normalize_ytdlp_chapters(ch: List[Dict[str, Any]], total_end: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, c in enumerate(ch or []):
        t = str(c.get("title") or "").strip()
        start = float(c.get("start_time") or c.get("start") or 0.0)
        end = float(c.get("end_time") or 0.0)
        if not end and i + 1 < len(ch):
            end = float(ch[i + 1].get("start_time") or 0.0)
        if not end:
            end = total_end or (start + 300.0)
        out.append({"title": t or f"Chapter {i+1}", "start": max(0.0, start), "end": max(start, end), "snippet": ""})
    return out

def _heuristic_chapters(spans: List[Tuple[float, float, str]]) -> List[Dict[str, Any]]:
    if not spans:
        return []
    spans = sorted(spans, key=lambda x: (x[0], x[1]))
    out: List[Dict[str, Any]] = []
    cur_s, cur_e, cur_txt = None, None, ""
    def flush():
        if cur_s is None or not cur_txt.strip():
            return
        snippet = " ".join(_SENT_SPLIT.split(cur_txt)[:2]).strip()[:220]
        out.append({"title": _title_from_text(cur_txt), "start": float(cur_s), "end": float(cur_e), "snippet": snippet})
    last_e = 0.0
    for s, e, t in spans:
        strong = bool(re.search(r"[.!?…]\s*$", t))
        long_gap = (s - last_e) > 60.0
        large = len(cur_txt) > 1000
        if cur_s is None:
            cur_s, cur_e, cur_txt = s, e, t
        elif long_gap or large or strong:
            flush()
            cur_s, cur_e, cur_txt = s, e, t
        else:
            cur_e = e
            cur_txt = (cur_txt + " " + t).strip()
        last_e = e
    flush()
    # szhat slishkom melkie
    merged: List[Dict[str, Any]] = []
    for ch in out:
        if merged and (ch["end"] - ch["start"]) < 45.0:
            merged[-1]["end"] = ch["end"]
            merged[-1]["snippet"] = (merged[-1]["snippet"] + " " + ch["snippet"]).strip()[:220]
        else:
            merged.append(ch)
    return merged

def _bump_state(key: str, delta: int):
    try:
        st = {}
        if os.path.isfile(_STATE):
            st = json.load(open(_STATE, "r", encoding="utf-8"))
        st[key] = int(st.get(key, 0)) + int(delta)
        st["ts"] = int(time.time())
        json.dump(st, open(_STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def build_chapters(dump_path: str, force: bool = False) -> Dict[str, Any]:
    cp = chapters_path(dump_path)
    if os.path.isfile(cp) and not force:
        try:
            return {"ok": True, "chapters": json.load(open(cp, "r", encoding="utf-8")), "cached": True, "path": cp}
        except Exception:
            pass
    j = _load_dump(dump_path)
    meta = (j.get("meta") or {}).get("yt_dlp") or {}
    dur = float(meta.get("duration") or 0.0)
    transcript = ((j.get("transcript") or {}).get("text") or "").strip()
    spans = _iter_spans(transcript)
    chapters = []
    if meta.get("chapters"):
        chapters = _normalize_ytdlp_chapters(meta.get("chapters") or [], total_end=dur or (spans[-1][1] if spans else 0.0))
    else:
        chapters = _heuristic_chapters(spans)
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    _bump_state("video_index_chapters_total", len(chapters))
    _bump_state("video_index_chapters_last_ts", 0)  # obnovim ts; samo znachenie nam ne vazhno
# return {"ok": True, "chapters": chapters, "cached": False, "path": cp}