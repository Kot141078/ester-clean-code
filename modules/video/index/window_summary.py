# -*- coding: utf-8 -*-
"""modules/video/index/window_summary.py - summarizatsiya po oknu taymlayna (start..end) iz dampa video.

Funktsii:
  • summarize(dump_path:str, start:float, end:float, max_chars:int=700) -> dict

A/B-slot (bezopasnaya samo-redaktura):
  • A (defolt): often-pozitsionnaya evristika (pervye predlozheniya + klyuchevye).
  • B: usilennaya evristika (TF-ish ves + “razreshenie” na chut bolee dlinnye frazy), format otveta sovmestim.

Mosty:
- Yavnyy: (Video ↔ Memory) vydaem kompaktnyy “zum” po vybrannomu fragmentu dlya RAG/otveta polzovatelyu.
- Skrytyy #1: (Infoteoriya ↔ Kachestvo) ogranichenie dliny/filtratsiya stop-slov umenshaet noise.
- Skrytyy #2: (Logika ↔ UX) okno zadaetsya sekundami, chto legko svyazat s pleerom i glavami.

Zemnoy abzats:
Eto “lupa”: na vybrannom otrezke bystro delaem konspekt, chtoby ne peresmatrivat vse video.

# c=a+b"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

VIDEO_QA_SUMMARY_AB = (os.getenv("VIDEO_QA_SUMMARY_AB", "A") or "A").upper()

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")

_TS_VTT = re.compile(r"\[\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]\]")
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?\…])\s+")
_STOP = set("a an the and or but if then else of on in to for with as is are was were be been being this that these those from by not no yes do does did at it its it's we you they i he she his her their our your about into over under out more most less least many much any some such can may might should would".split()
             + "i v vo ne chto on na ya s so kak a to vse ona tak ego no da ty k u zhe vy za by po ee mne est oni byt byl byla bylo byli iz u nas ot zhe li ili dazhe lish esche pri".split())

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
    if not rows and text.strip():
        rows.append((0.0, 10**9, text.strip()))
    return rows

def _sentences_in_window(spans: List[Tuple[float, float, str]], start: float, end: float) -> List[str]:
    buf: List[str] = []
    for s, e, t in spans:
        if e < start or s > end:
            continue
        for sent in _SENT_SPLIT.split(t):
            ss = sent.strip()
            if ss:
                buf.append(ss)
    return buf

def _score_tokens(s: str) -> float:
    toks = re.findall(r"[a-zA-Za-yaA-YaeE0-9\-]+", s.lower())
    toks = [t for t in toks if t not in _STOP and len(t) > 2]
    return sum(1.0 for _ in toks)

def _summarize_A(sents: List[str], max_chars: int) -> str:
    if not sents:
        return ""
    # first 1–2 sentences + 2–3 “saturated”
    out: List[str] = []
    for s in sents[:2]:
        out.append(s)
    scored = sorted((( _score_tokens(s), i, s) for i, s in enumerate(sents)), reverse=True)
    for _, _, s in scored:
        if s in out:
            continue
        out.append(s)
        if len(" ".join(out)) > max_chars:
            break
        if len(out) >= 5:
            break
    text = " ".join(out)[:max_chars].strip()
    return text

def _summarize_B(sents: List[str], max_chars: int) -> str:
    # enhanced heuristic: favor longer informative sentences, avoiding repetitions
    scored = sorted((( _score_tokens(s) * (1.0 + min(len(s), 200)/200.0), i, s) for i, s in enumerate(sents)), reverse=True)
    out: List[str] = []
    for _, _, s in scored:
        if any(s in x or x in s for x in out):
            continue
        out.append(s)
        if len(" ".join(out)) > max_chars:
            break
        if len(out) >= 6:
            break
    if not out and sents:
        out = sents[:2]
    return " ".join(out)[:max_chars].strip()

def summarize(dump_path: str, start: float, end: float, max_chars: int = 700) -> Dict[str, Any]:
    j = json.load(open(dump_path, "r", encoding="utf-8"))
    text = ((j.get("transcript") or {}).get("text") or "").strip()
    spans = _iter_spans(text)
    sents = _sentences_in_window(spans, start, end)
    if VIDEO_QA_SUMMARY_AB == "B":
        out = _summarize_B(sents, max_chars)
    else:
        out = _summarize_A(sents, max_chars)
# return {"ok": True, "start": float(start), "end": float(end), "summary": out}