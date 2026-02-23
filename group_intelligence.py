# -*- coding: utf-8 -*-
from __future__ import annotations

"""
group_intelligence.py
Mozg «umnogo uchastnika» dlya gruppovykh chatov Telegram.

Novoe:
- uchet «vidimykh» grupp i ikh svezhesti (groups_seen.json)
- utilita list_active_groups() dlya vechernikh demonov
"""

import json
import os
import random
import re
import time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_DIR = os.path.join("state")
os.makedirs(STATE_DIR, exist_ok=True)

# --- parametry povedeniya v gruppe ---
MIN_INTERVAL_SEC = 50  # ne chasche etogo dlya odnoy gruppy
SILENCE_TRIGGER_SEC = (
    300  # esli 5 minut tishiny — mozhno razmorozit
)
EMOTION_SPIKE = 0.72  # trevoga/zlost/radost vyshe poroga
TOPIC_CHANGE_THRESHOLD = 0.55
TOPIC_WINDOW = 30  # skolko poslednikh soobscheniy uchityvaem
MAX_REPLY_LEN = 600

# legkiy slovar tem
TOPIC_DICT = {
    "zdorove": {
        "vrach",
        "analiz",
        "davlenie",
        "tablet",
        "poliklin",
        "bol",
        "temperat",
        "prostud",
        "kashlya",
        "bolit",
    },
    "puteshestviya": {
        "bilet",
        "poezdka",
        "samol",
        "viza",
        "granits",
        "otel",
        "aeroport",
    },
    "dom/byt": {
        "remont",
        "schet",
        "kommun",
        "ubork",
        "pylesos",
        "stirk",
        "svet",
        "gaz",
    },
    "eda": {
        "retsept",
        "uzhin",
        "obed",
        "kukhn",
        "produkt",
        "magazin",
        "kofe",
        "chay",
    },
    "rabota/ucheba": {
        "rabot",
        "proek",
        "srok",
        "dz",
        "domashk",
        "sobes",
        "otchet",
        "sess",
    },
    "finansy": {
        "karta",
        "bank",
        "perevod",
        "snyat",
        "oplat",
        "kredit",
        "dolg",
        "kesh",
    },
    "kino/ser": {"film", "serial", "seriya", "kino", "kinet"},
    "sport": {
        "futbol",
        "sport",
        "probezh",
        "yoga",
        "trenir",
        "zal",
    },
}

HELP_CUES = {
    "mozhesh",
    "pomogi",
    "podskazhi",
    "kak",
    "chto delat",
    "chto posovetuesh",
    "ideyu",
    "sovet",
}


# --- fayly sostoyaniya ---
def _group_path(chat_id: int) -> str:
    return os.path.join(STATE_DIR, f"group_{chat_id}.json")


def _topics_path(chat_id: int) -> str:
    return os.path.join(STATE_DIR, f"group_topics_{chat_id}.json")


GROUPS_SEEN_PATH = os.path.join(STATE_DIR, "groups_seen.json")


# --- tekh. utility ---
def _load(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def _save(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now() -> float:
    return time.time()


def _extract_topics(text: str) -> List[str]:
    t = text.lower()
    found = []
    for k, stems in TOPIC_DICT.items():
        if any(st in t for st in stems):
            found.append(k)
    return found[:3]


def _is_question(text: str) -> bool:
    if "?" in text:
        return True
    t = text.lower()
    return any(cue in t for cue in HELP_CUES)


def _topic_similarity(a: List[str], b: List[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    uni = len(sa | sb)
    if uni == 0:
        return 0.0
    return inter / uni


# --- publichnye funktsii yadra ---


def record_message(chat_id: int, author: str, text: str, emotions: Dict[str, float]):
    """Zapisat soobschenie v okno tem + otmetit gruppu kak aktivnuyu."""
    meta = _load(_group_path(chat_id))
    msgs: List[Dict[str, Any]] = meta.get("msgs", [])
    topic = _extract_topics(text)
    rec = {
        "ts": _now(),
        "author": author,
        "text": text,
        "emotions": emotions,
        "topic": topic,
    }
    msgs.append(rec)
    msgs = msgs[-TOPIC_WINDOW:]
    meta["msgs"] = msgs
    meta["last_ts"] = rec["ts"]
    meta["last_author"] = author
    _save(_group_path(chat_id), meta)

    agg = _load(_topics_path(chat_id))
    for t in topic:
        agg[t] = int(agg.get(t, 0)) + 1
    _save(_topics_path(chat_id), agg)

    # otmetim gruppu «vidimoy»
    seen = _load(GROUPS_SEEN_PATH)
    seen[str(chat_id)] = {"last_seen_ts": _now()}
    _save(GROUPS_SEEN_PATH, seen)


def group_snapshot(chat_id: int) -> Dict[str, Any]:
    meta = _load(_group_path(chat_id))
    agg = _load(_topics_path(chat_id))
    return {
        "last_ts": meta.get("last_ts"),
        "last_author": meta.get("last_author"),
        "count": len(meta.get("msgs", [])),
        "topics_agg": agg,
    }


def chat_topics(chat_id: int, topn: int = 5) -> List[Tuple[str, int]]:
    agg = _load(_topics_path(chat_id))
    items = sorted(agg.items(), key=lambda x: x[1], reverse=True)
    return items[:topn]


def list_active_groups(active_within_sec: int = 24 * 3600) -> List[int]:
    """Gruppy, gde byli soobscheniya za poslednie N sekund."""
    seen = _load(GROUPS_SEEN_PATH)
    now = _now()
    out = []
    for k, v in (seen or {}).items():
        try:
            if now - float(v.get("last_seen_ts", 0)) <= active_within_sec:
                out.append(int(k))
        except Exception:
            pass
    return out


def _passed_rate_limit(chat_id: int) -> bool:
    meta = _load(_group_path(chat_id))
    last = float(meta.get("last_reply_ts", 0))
    if _now() - last >= MIN_INTERVAL_SEC + random.randint(-10, 10):
        return True
    # tishina — mozhno razmorozit
    last_msg = float(meta.get("last_ts", 0))
    if last_msg and _now() - last_msg >= SILENCE_TRIGGER_SEC:
        return True
    return False


def _mark_replied(chat_id: int):
    meta = _load(_group_path(chat_id))
    meta["last_reply_ts"] = _now()
    _save(_group_path(chat_id), meta)


def should_respond(chat_id: int, author: str, text: str, emotions: Dict[str, float]) -> bool:
    if not _passed_rate_limit(chat_id):
        return False
    if _is_question(text):
        return True
    if (
        max(
            float(emotions.get("anxiety", 0)),
            float(emotions.get("anger", 0)),
            float(emotions.get("joy", 0)),
        )
        >= EMOTION_SPIKE
    ):
        return True
    meta = _load(_group_path(chat_id))
    prev_msgs = meta.get("msgs", [])
    prev_topic = prev_msgs[-1]["topic"] if prev_msgs else []
    cur_topic = _extract_topics(text)
    sim = _topic_similarity(prev_topic, cur_topic)
    if sim <= TOPIC_CHANGE_THRESHOLD and (cur_topic or prev_topic):
        return True
    last_ts = float(meta.get("last_ts", 0))
    if last_ts and _now() - last_ts >= SILENCE_TRIGGER_SEC:
        return True
    return False


def _summarize_window(msgs: List[Dict[str, Any]], last_n: int = 8) -> str:
    msgs = msgs[-last_n:]
    authors = [m["author"] for m in msgs]
    who = ", ".join(sorted(set(authors), key=authors.count, reverse=True))[:50]
    agg = {}
    for m in msgs:
        for t in m.get("topic", []):
            agg[t] = agg.get(t, 0) + 1
    top_topics = ", ".join(
        [k for k, _ in sorted(agg.items(), key=lambda x: x[1], reverse=True)[:3]]
    )
    parts = []
    if top_topics:
        parts.append(f"obsuzhdaem: {top_topics}")
    if who:
        parts.append(f"aktivny: {who}")
    return " · ".join(parts)


def compose_response(chat_id: int, author: str, text: str, emotions: Dict[str, float]) -> str:
    meta = _load(_group_path(chat_id))
    msgs = meta.get("msgs", [])
    topic_now = _extract_topics(text)
    summary = _summarize_window(msgs, last_n=8) if msgs else ""

    anx = float(emotions.get("anxiety", 0))
    joy = float(emotions.get("joy", 0))
    anger = float(emotions.get("anger", 0))

    if _is_question(text):
        reply = "Poprobuyu korotko: "
        if "vrach" in " ".join(topic_now):
            reply += "proverte vremya/adres, vozmite dokument i strakhovku. Nuzhno taksi — skazhite."
        elif "bilet" in text.lower():
            reply += "sravnite varianty v agregatorakh, obratite vnimanie na peresadki i bagazh."
        else:
            reply += "mogu nakinut 2–3 varianta resheniya — esli nuzhno, utochnite, chto uzhe probovali."
        if summary:
            reply += f"\n<i>{summary}</i>"
        _mark_replied(chat_id)
        return reply[:MAX_REPLY_LEN]

    if max(anx, anger) >= EMOTION_SPIKE:
        reply = "Davayte na minutku vydokhnem. Ya ryadom. "
        reply += "Vdokh 4 — pauza 4 — vydokh 6. Potom reshim shag za shagom."
        if summary:
            reply += f"\n<i>{summary}</i>"
        _mark_replied(chat_id)
        return reply[:MAX_REPLY_LEN]

    if joy >= EMOTION_SPIKE:
        reply = "Zvuchit klassno! 🎉 Chto zakrepim kak sleduyuschiy shag?"
        if summary:
            reply += f"\n<i>{summary}</i>"
        _mark_replied(chat_id)
        return reply[:MAX_REPLY_LEN]

    prev_topic = msgs[-1]["topic"] if msgs else []
    sim = 0.0
    if prev_topic or topic_now:
        sim = len(set(prev_topic) & set(topic_now)) / max(1, len(set(prev_topic) | set(topic_now)))
    if sim <= TOPIC_CHANGE_THRESHOLD and (topic_now or prev_topic):
        prev_label = ", ".join(prev_topic) or "predyduschaya tema"
        now_label = ", ".join(topic_now) or "novaya tema"
        reply = f"Pokhozhe, my pereskochili s «{prev_label}» na «{now_label}». Nuzhen mostik?"
        if summary:
            reply += f"\n<i>{summary}</i>"
        _mark_replied(chat_id)
        return reply[:MAX_REPLY_LEN]

    last_ts = float(meta.get("last_ts", 0))
    if last_ts and time.time() - last_ts >= SILENCE_TRIGGER_SEC:
        reply = "Nemnogo zatikhli. Mogu sobrat korotkoe rezyume i varianty sleduyuschikh shagov."
        if summary:
            reply += f"\n<i>{summary}</i>"
        _mark_replied(chat_id)
        return reply[:MAX_REPLY_LEN]

    base = "Esli khotite — predlozhu malenkiy shag tak, chtoby stalo chut legche/ponyatnee."
    if summary:
        base += f"\n<i>{summary}</i>"
    _mark_replied(chat_id)
    return base[:MAX_REPLY_LEN]