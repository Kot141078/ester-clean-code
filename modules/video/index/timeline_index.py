# -*- coding: utf-8 -*-
"""modules/video/index/timeline_index.py - postroenie taymlaynovogo index iz video dump + vektorizatsiya segmentov.

What does it do:
  • build_index(dump_path, ...) → JSONL-indexes segmentov s taymkodami, metadannymi i registratsiey v vektornom sloe.
  • list_dumps() → perechislenie rep_*.json i nalichie .index.jsonl.
  • qa_scope_filter(items, scope) → post-filtr rezultatov gibridnogo poiska po meta-tegu dump_id.

A/B (bezopasnaya samo-redaktura):
  • A (defolt): regulyarnaya narezka po vremeni (VIDEO_INDEX_CHUNK_SEC) s perekrytiem (VIDEO_INDEX_OVERLAP_SEC),
                opirayas na taymkody v subtitrakh (esli est), inache - na razmer/punktatsiyu.
  • B: evristicheskaya segmentatsiya po pauzam/punktuatsii/taymkodam (bolee krupnye smyslovye bloki), avto-otkat ne nuzhen,
       tak kak A i B vybirayutsya ENV i ne lomayut kontrakty.

Faily:
  • data/video_ingest/rep_*.json - iskhodnyy dump (sozdaet universal extractor).
  • data/video_ingest/index/<dump_id>.index.jsonl - segmenty. Odin JSON v stroke:
      {"id","start","end","text","meta":{"src":{"url|path"},"dump_id","tags":[...]}}
  • data/video_ingest/index/state.json — schetchiki i sluzhebnye otmetki.

Mosty:
- Yavnyy: (Memory ↔ Poisk) formiruem edinitsy RAG po video dlya otveta na voprosy s privyazkoy ko vremeni.
- Skrytyy #1: (Infoteoriya ↔ Inzheneriya) stabilnaya skhema segmenta delaet retriv prostym i predskazuemym.
- Skrytyy #2: (Logika ↔ UX) segmenty soderzhat ssylku `url_ts`, chtoby srazu prygnut k mestu v video.

Zemnoy abzats:
This is “narezchik batonov”: bolshoy rolik rezhem na lomtiki s metkami vremeni i kladem na polku - potom legko nayti nuzhnyy kusok.

# c=a+b"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, Iterable, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")
INDEX_DIR = os.path.join(DATA_DIR, "index")
os.makedirs(INDEX_DIR, exist_ok=True)

VIDEO_INDEX_AB = (os.getenv("VIDEO_INDEX_AB", "A") or "A").upper()
CHUNK_SEC = int(os.getenv("VIDEO_INDEX_CHUNK_SEC", "60"))
OVERLAP_SEC = int(os.getenv("VIDEO_INDEX_OVERLAP_SEC", "6"))
MAX_CHARS = int(os.getenv("VIDEO_INDEX_MAXCHARS", "1200"))

_STATE = os.path.join(INDEX_DIR, "state.json")

def _load_dump(path: str) -> Dict[str, Any]:
    return json.load(open(path, "r", encoding="utf-8"))

def _dump_id(path: str) -> str:
    base = os.path.basename(path)
    return os.path.splitext(base)[0]  # rep_1699999999 → rep_1699999999

_TS_VTT = re.compile(r"\[\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]\]")

def _hms_to_sec(hms: str) -> float:
    hh, mm, ss = hms.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)

def _sec_to_hms(sec: float) -> str:
    s = max(0, float(sec))
    hh = int(s // 3600); s -= hh * 3600
    mm = int(s // 60); s -= mm * 60
    return f"{hh:02d}:{mm:02d}:{s:06.3f}"

def _iter_spans_from_text(text: str) -> List[Tuple[float, float, str]]:
    """We are trying to extract juststart,end from the markers yuyuh:mm:s.mmm --> xx:mm:s.mmmshsch.
    If not, it will return yu(0, +inf, text)sch."""
    rows: List[Tuple[float, float, str]] = []
    if not text.strip():
        return rows
    blocks = re.split(r"\n+", text.strip())
    for b in blocks:
        m = _TS_VTT.search(b)
        t = re.sub(_TS_VTT, "", b).strip()
        if m and t:
            start = _hms_to_sec(m.group(1))
            end = _hms_to_sec(m.group(2))
            rows.append((start, end, t))
    if rows:
        return rows
    # fake: no timecodes - let's make one big block
    return [(0.0, 10 ** 9, text.strip())]

def _merge_sentences(sentences: List[Tuple[float, float, str]], max_chars: int) -> List[Tuple[float, float, str]]:
    out: List[Tuple[float, float, str]] = []
    cur_s, cur_e, cur_t = None, None, ""
    for s, e, t in sentences:
        if cur_s is None:
            cur_s, cur_e, cur_t = s, e, t
            continue
        if len(cur_t) + 1 + len(t) <= max_chars:
            cur_e = e
            cur_t = (cur_t + " " + t).strip()
        else:
            out.append((float(cur_s), float(cur_e), cur_t))
            cur_s, cur_e, cur_t = s, e, t
    if cur_s is not None and cur_t:
        out.append((float(cur_s), float(cur_e), cur_t))
    return out

def _segments_A(spans: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
    """A: we cut into equal windows CHUNK_SES with overlap OVERLAP_SEC, using real start/end if available."""
    if not spans:
        return []
    # flatten into one stream in time
    spans = sorted(spans, key=lambda x: (x[0], x[1]))
    t0 = spans[0][0]
    t1 = max([x[1] for x in spans])
    win = float(CHUNK_SEC)
    ovl = float(OVERLAP_SEC)
    segments: List[Tuple[float, float, str]] = []
    t = t0
    text_all = []
    for s, e, ttxt in spans:
        text_all.append((s, e, ttxt))
    while t < t1 + 1e-6:
        w_start, w_end = t, t + win
        buf = [tt for (s, e, tt) in text_all if not (e < w_start or s > w_end)]
        if buf:
            segments.append((w_start, w_end, " ".join(buf)))
        t += (win - ovl)
    return _merge_sentences(segments, MAX_CHARS)

def _segments_B(spans: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
    """B: evristicheskaya segmentatsiya po pauzam/punktuatsii.
    - slivaem podryad iduschie stroki, poka ne vstretim “silnuyu” punktuatsiyu (".", "!", "?", "…") ili dlinnuyu pauzu (>15s)."""
    if not spans:
        return []
    spans = sorted(spans, key=lambda x: (x[0], x[1]))
    out: List[Tuple[float, float, str]] = []
    cur_s, cur_e, cur_t = None, None, ""
    for s, e, t in spans:
        if cur_s is None:
            cur_s, cur_e, cur_t = s, e, t
            continue
        strong = bool(re.search(r"[.!?…]\s*$", cur_t))
        long_gap = (s - (cur_e or s)) > 15.0
        if strong or long_gap or (len(cur_t) + len(t) > MAX_CHARS):
            out.append((float(cur_s), float(cur_e), cur_t.strip()))
            cur_s, cur_e, cur_t = s, e, t
        else:
            cur_e = e
            cur_t = (cur_t + " " + t).strip()
    if cur_s is not None and cur_t:
        out.append((float(cur_s), float(cur_e), cur_t.strip()))
    return out

def _youtube_ts(url: str, start: float) -> str:
    try:
        if "youtu" in url:
            sec = int(max(0, start))
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}t={sec}s"
    except Exception:
        pass
    return url

def build_index(dump_path: str) -> Dict[str, Any]:
    j = _load_dump(dump_path)
    src = j.get("source") or {}
    url = (src.get("url") or "").strip()
    text = ((j.get("transcript") or {}).get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "dump has no transcript text"}
    spans = _iter_spans_from_text(text)
    segs = _segments_A(spans) if VIDEO_INDEX_AB == "A" else _segments_B(spans)
    dump_id = _dump_id(dump_path)
    index_path = os.path.join(INDEX_DIR, f"{dump_id}.index.jsonl")
    n = 0
    with open(index_path, "w", encoding="utf-8") as f:
        for s, e, t in segs:
            if not t.strip():
                continue
            seg_id = f"{dump_id}#t={int(max(0, s))}"
            meta = {"src": src, "dump_id": dump_id, "start": float(s), "end": float(e), "url_ts": _youtube_ts(url, s)}
            row = {"id": seg_id, "start": s, "end": e, "text": t[:MAX_CHARS], "meta": meta, "tags": ["video", "segment", f"dump:{dump_id}"]}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    # vektorizatsiya (best-effort)
    try:
        from modules.memory.vector_reconcile import reconcile  # type: ignore
        items = []
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                j = json.loads(line)
                items.append({"id": j["id"], "text": j["text"], "tags": ["video", "segment", f"dump:{dump_id}"], "meta": j["meta"]})
        if items:
            reconcile(items)
    except Exception:
        pass
    _bump_state("dumps_indexed_total", +1)
    _bump_state("segments_total", n)
    return {"ok": True, "dump_id": dump_id, "segments_indexed": n, "index": index_path}

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

def list_dumps() -> List[Dict[str, Any]]:
    if not os.path.isdir(DATA_DIR):
        return []
    rows = []
    for name in os.listdir(DATA_DIR):
        if not (name.startswith("rep_") and name.endswith(".json")):
            continue
        dump = os.path.join(DATA_DIR, name)
        dump_id = _dump_id(dump)
        idx = os.path.join(INDEX_DIR, f"{dump_id}.index.jsonl")
        rows.append({"dump": dump, "dump_id": dump_id, "indexed": bool(os.path.isfile(idx)), "index": idx if os.path.isfile(idx) else None})
    rows.sort(key=lambda x: x["dump"], reverse=True)
    return rows

def qa_scope_filter(items: List[Dict[str, Any]], scope: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not scope:
        return items
    want_dump = None
    if "dump" in scope and scope["dump"]:
        want_dump = _dump_id(scope["dump"])
    elif "dump_id" in scope and scope["dump_id"]:
        want_dump = scope["dump_id"]
    if not want_dump:
        return items
    out: List[Dict[str, Any]] = []
    for it in items:
        meta = it.get("meta") or {}
        if (meta.get("dump_id") == want_dump) or (f"dump:{want_dump}" in (it.get("tags") or [])):
            out.append(it)
# return out