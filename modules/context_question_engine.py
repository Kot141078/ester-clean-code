# -*- coding: utf-8 -*-
"""
modules/context_question_engine.py — Kontekstnyy dvizhok voprosov (CTXQ)

YaVNYY MOST:
  c = a + b  (chelovek + protsedury) → vopros kak «myagkiy interfeys» mezhdu zhivym opytom i mashinnym planom.

SKRYTYE MOSTY:
  - Ashby (requisite variety): neskolko istochnikov signalov (dialog, sobytiya, vremya sutok) dayut raznoobrazie,
    a prioritizatsiya/kuldauny — stabilizatsiyu.
  - Cover & Thomas (infoteoriya): kontekst — eto kanal s ogranichennoy propusknoy sposobnostyu;
    poetomu my «szhimaem» istoriyu do tem/sobytiy i derzhim zhestkie limity na obem vkhoda.
  - Dkhammapada (pravilnaya rech): vopros dolzhen byt umestnym, myagkim i ne razduvat um «pustym shumom».

ZEMNOY ABZATs (anatomiya/inzheneriya):
  Etot modul — kak dykhatelnyy tsentr v prodolgovatom mozge: on ne «dumaet za koru», no zadaet ritm.
  Esli ritm sbit (povtoryaem voprosy, slishkom dlinnye prompty, «peregruzka»), nachinaetsya «odyshka»
  — otvety rvutsya. CTXQ derzhit chastotu i obem, chtoby sistema ne ukhodila v aritmiyu konteksta.

Naznachenie:
  - Bystro (evristiki) analizirovat istoriyu dialoga (JSONL scroll), vydelyat temy/sobytiya
  - Adaptirovat formulirovku k vremeni sutok (utro/den/vecher/noch)
  - Prioritizirovat sobytiya (daty, vazhnye povody)
  - Davat bezopasnyy A/B rezhim: A=tolko fakty/evristiki, B=optsionalno (esli sverkhu dayut LLM-funktsiyu),
    s avto-otkatom k A pri lyubom sboe.

Trebovaniya: tolko stdlib.
"""

from __future__ import annotations

import os
import re
import json
import time
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


_STOPWORDS_RU = {
    "i", "v", "vo", "ne", "chto", "on", "na", "ya", "s", "so", "kak", "a", "to",
    "vse", "ona", "tak", "ego", "no", "da", "ty", "k", "u", "zhe", "vy", "za",
    "by", "po", "tolko", "ee", "mne", "bylo", "vot", "ot", "menya", "esche",
    "net", "o", "iz", "emu", "teper", "kogda", "dazhe", "nu", "vdrug",
    "li", "esli", "uzhe", "ili", "ni", "byt", "byl", "nego", "do", "vas",
    "nibud", "opyat", "uzh", "vam", "ved", "tam", "potom", "sebya", "nichego",
    "ey", "mozhet", "oni", "tut", "gde", "est", "nado", "ney", "dlya", "my",
    "tebya", "ikh", "chem", "byla", "sam", "chtob", "bez", "budto", "chego",
    "raz", "tozhe", "sebe", "pod", "budet", "zh", "togda", "kto", "etot",
    "togo", "potomu", "etogo", "kakoy", "sovsem", "nim", "zdes",
}

_TOKEN_RE = re.compile(r"[A-Za-zA-Yaa-yaEe0-9_]{2,}", re.UNICODE)

_DATE_DDMM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b")
_BDAY_WORD = re.compile(r"\b(den\s+rozhd\w+|birthday)\b", re.IGNORECASE)
_MONTHS_RU = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "ma": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentyabr": 9, "oktyabr": 10, "noyabr": 11, "dekabr": 12,
}


def _now_local() -> datetime:
    # Closed-box: opiraemsya na lokalnoe vremya mashiny.
    return datetime.now()


def _time_of_day(dt: datetime) -> str:
    h = dt.hour
    if 5 <= h < 11:
        return "morning"
    if 11 <= h < 17:
        return "day"
    if 17 <= h < 22:
        return "evening"
    return "night"


def _hash_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def _clamp_text(s: str, max_chars: int) -> str:
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "..."


def _read_tail_lines(path: str, max_lines: int = 300, max_bytes: int = 1_500_000) -> List[str]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read_size = min(size, max_bytes)
            f.seek(-read_size, os.SEEK_END)
            data = f.read(read_size)
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if size > read_size and lines:
            lines = lines[1:]
        return lines[-max_lines:]
    except Exception:
        return []


@dataclass
class Event:
    kind: str
    score: float
    payload: Dict[str, Any]


@dataclass
class Topic:
    name: str
    score: float


@dataclass
class Suggestion:
    question: str
    priority: float
    tod: str
    topics: List[Topic]
    events: List[Event]
    debug: Dict[str, Any]


class DialogAnalyzer:
    def __init__(self, scroll_path: str, max_lines: int = 250):
        self.scroll_path = scroll_path
        self.max_lines = max_lines

    def read_recent(self) -> List[Dict[str, Any]]:
        raw_lines = _read_tail_lines(self.scroll_path, max_lines=self.max_lines)
        items: List[Dict[str, Any]] = []
        for ln in raw_lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
                if isinstance(obj, dict) and "content" in obj:
                    items.append(obj)
            except Exception:
                continue
        return items

    def extract_topics(self, items: List[Dict[str, Any]], top_k: int = 8) -> List[Topic]:
        freq: Dict[str, int] = {}
        for it in items:
            txt = str(it.get("content", "") or "")
            for tok in _TOKEN_RE.findall(txt):
                t = tok.lower()
                if t in _STOPWORDS_RU:
                    continue
                if t.isdigit():
                    continue
                freq[t] = freq.get(t, 0) + 1

        boosts = {
            "ester": 2, "liah": 2, "liya": 2, "telegram": 2, "bot": 2,
            "advokat": 2, "yurist": 2, "sud": 2, "kontrakt": 2,
            "gpu": 2, "rtx": 2, "nvidia": 2, "vram": 2, "chroma": 2,
        }
        scored: List[Tuple[str, float]] = []
        for w, c in freq.items():
            b = boosts.get(w, 0)
            scored.append((w, float(c + b)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [Topic(name=w, score=s) for w, s in scored[:top_k]]

    def extract_events(self, items: List[Dict[str, Any]]) -> List[Event]:
        events: List[Event] = []
        joined = "\n".join(str(it.get("content", "") or "") for it in items[-80:])

        if _BDAY_WORD.search(joined):
            for m in _DATE_DDMM.finditer(joined):
                d = int(m.group(1))
                mo = int(m.group(2))
                y = m.group(3)
                yy = int(y) if y else None
                events.append(Event(kind="birthday", score=10.0, payload={"day": d, "month": mo, "year": yy}))

            for m in re.finditer(r"\b(\d{1,2})\s+([A-Yaa-yaEe]+)\b", joined):
                d = int(m.group(1))
                mn = m.group(2).lower()
                for stem, mo in _MONTHS_RU.items():
                    if mn.startswith(stem):
                        events.append(Event(kind="birthday", score=10.0, payload={"day": d, "month": mo, "year": None}))
                        break

        if re.search(r"\b(duchesse|srl|plainte|avocat|contrôle|lois\s+sociales)\b", joined, re.IGNORECASE):
            events.append(Event(kind="legal", score=7.0, payload={"hint": "legal_dispute"}))

        if re.search(r"\b(peregruzk\w+\s+kontekst\w+|context\s+length|out\s+of\s+memory|vram|409\s+conflict)\b", joined, re.IGNORECASE):
            events.append(Event(kind="stability", score=6.0, payload={"hint": "overload_or_conflict"}))

        uniq: Dict[str, Event] = {}
        for e in events:
            key = f"{e.kind}:{json.dumps(e.payload, sort_keys=True, ensure_ascii=False)}"
            if key not in uniq or uniq[key].score < e.score:
                uniq[key] = e
        return sorted(list(uniq.values()), key=lambda e: e.score, reverse=True)


class ContextState:
    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, Any] = {
            "known": {},
            "last_question_hash": "",
            "last_question_ts": 0,
            "cooldown_sec": 1800,
        }
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                    obj = json.load(f)
                if isinstance(obj, dict):
                    self.data.update(obj)
        except Exception:
            pass

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def update_known(self, events: List[Event]) -> None:
        for e in events:
            if e.kind == "birthday" and e.payload.get("day") and e.payload.get("month"):
                self.data.setdefault("known", {})["birthday"] = {"day": e.payload["day"], "month": e.payload["month"]}
            if e.kind == "legal":
                self.data.setdefault("known", {})["legal_dispute"] = True

    def can_ask(self, question: str, now_ts: Optional[int] = None) -> bool:
        now_ts = int(now_ts or time.time())
        cooldown = int(self.data.get("cooldown_sec", 1800))
        last_ts = int(self.data.get("last_question_ts", 0))
        if now_ts - last_ts < cooldown:
            return False
        h = _hash_text(question.strip())
        if h and h == (self.data.get("last_question_hash") or ""):
            return False
        return True

    def mark_asked(self, question: str, now_ts: Optional[int] = None) -> None:
        now_ts = int(now_ts or time.time())
        self.data["last_question_ts"] = now_ts
        self.data["last_question_hash"] = _hash_text(question.strip())
        self.save()


class TimeAdapter:
    def style_prefix(self, tod: str) -> str:
        if tod == "morning":
            return "Dobroe utro. "
        if tod == "day":
            return ""
        if tod == "evening":
            return "Dobryy vecher. "
        return "Noch — vremya tishiny. "


class QuestionGenerator:
    def __init__(self):
        self.time_adapter = TimeAdapter()

    def _priority_for_events(self, events: List[Event], now: datetime, known: Dict[str, Any]) -> Tuple[Optional[Event], float]:
        b = known.get("birthday") if isinstance(known, dict) else None
        if b and b.get("day") and b.get("month"):
            try:
                d = int(b["day"]); mo = int(b["month"])
                this_year = now.year
                target = datetime(this_year, mo, d)
                if target < now.replace(tzinfo=None):
                    target = datetime(this_year + 1, mo, d)
                days = (target.date() - now.date()).days
                score = 12.0 if days == 0 else (9.0 if days <= 7 else (6.0 if days <= 14 else 0.0))
                if score > 0:
                    return Event(kind="birthday", score=score, payload={"day": d, "month": mo, "days_left": days}), score
            except Exception:
                pass

        if events:
            return events[0], float(events[0].score)
        return None, 0.0

    def _question_for_event(self, e: Event, tod: str, user_name: str) -> str:
        pref = self.time_adapter.style_prefix(tod)
        if e.kind == "birthday":
            days = e.payload.get("days_left")
            if days == 0:
                return pref + f"{user_name}, s dnem rozhdeniya! Kak khochesh provesti etot den? Est li chto-to, chto mne vazhno uchest?"
            if isinstance(days, int) and days <= 7:
                return pref + f"{user_name}, u tebya skoro den rozhdeniya (cherez {days} dn.). Khochesh zaranee nametit, chto dlya tebya vazhno v etot period?"
            return pref + f"{user_name}, napomni, pozhaluysta, kak ty khochesh otmechat svoy den rozhdeniya (v spokoynom ili v aktivnom rezhime)?"

        if e.kind == "legal":
            if tod in ("evening", "night"):
                return pref + f"{user_name}, khochesh spokoyno podvesti itog po yuridicheskoy istorii za segodnya: chto prodvinulos, a chto trevozhit?"
            return pref + f"{user_name}, po delu s rabotodatelem/DUCHESSE: kakoy sleduyuschiy shag dlya tebya seychas samyy vazhnyy?"

        if e.kind == "stability":
            return pref + f"{user_name}, vizhu priznaki peregruza/konflikta v sisteme. Chto seychas vazhnee: stabilnost (menshe shumnykh protsessov) ili skorost eksperimentov?"

        return pref + f"{user_name}, chto seychas dlya tebya samoe prioritetnoe?"

    def _question_for_topics(self, topics: List[Topic], tod: str, user_name: str) -> str:
        pref = self.time_adapter.style_prefix(tod)
        top = topics[0].name if topics else ""
        if tod == "morning":
            return pref + (f"{user_name}, kakie plany na den po teme «{top}»? Chto dolzhno byt sdelano obyazatelno?" if top else f"{user_name}, kakie 1–2 zadachi segodnya samye vazhnye?")
        if tod == "day":
            return pref + (f"{user_name}, po teme «{top}» — chto seychas bolshe vsego meshaet ili trebuet resheniya?" if top else f"{user_name}, na chem seychas fokus: proekt, byt ili vosstanovlenie?")
        if tod == "evening":
            return pref + (f"{user_name}, kak proshel den po teme «{top}»? Chto poluchilos, a chto luchshe perenesti?" if top else f"{user_name}, khochesh korotko razobrat den: chto dat pamyati, a chto otpustit?")
        return pref + (f"{user_name}, pered snom: est odna vesch po «{top}», kotoruyu stoit ostavit kak anchor na zavtra?" if top else f"{user_name}, noch. Khochesh tishiny ili odin korotkiy vopros po delu?")

    def generate(self, now: datetime, user_name: str, topics: List[Topic], events: List[Event], known: Dict[str, Any]) -> Suggestion:
        tod = _time_of_day(now)
        e, pr = self._priority_for_events(events, now, known)
        if e and pr >= 6.0:
            q = self._question_for_event(e, tod, user_name)
            return Suggestion(question=q, priority=pr, tod=tod, topics=topics, events=events, debug={"picked": "event", "event": asdict(e)})
        q = self._question_for_topics(topics, tod, user_name)
        pr2 = 3.0 if topics else 2.0
        return Suggestion(question=q, priority=pr2, tod=tod, topics=topics, events=events, debug={"picked": "topic"})


class ContextQuestionEngine:
    """
    Fasad.

    A/B:
      - ESTER_CTXQ_SLOT=A (default): tolko evristiki
      - ESTER_CTXQ_SLOT=B: esli peredana llm_fn, poprobuem B, inache avto-otkat k A
    """
    def __init__(
        self,
        project_root: str,
        memory_file: str,
        state_relpath: str = os.path.join("data", "state", "context_questions.json"),
        max_scroll_lines: int = 250,
        max_mem_chars: int = 4000,
        max_draft_chars: int = 2500,
        cooldown_sec: int = 1800,
        llm_fn: Optional[Any] = None,
    ):
        self.project_root = project_root or "."
        self.memory_file = memory_file
        self.state_path = os.path.join(self.project_root, state_relpath)
        self.analyzer = DialogAnalyzer(self.memory_file, max_lines=max_scroll_lines)
        self.generator = QuestionGenerator()
        self.state = ContextState(self.state_path)
        self.state.data["cooldown_sec"] = int(cooldown_sec)
        self.max_mem_chars = int(max_mem_chars)
        self.max_draft_chars = int(max_draft_chars)
        self.llm_fn = llm_fn

    def _suggest_A(self, user_name: str) -> Suggestion:
        now = _now_local()
        items = self.analyzer.read_recent()
        topics = self.analyzer.extract_topics(items)
        events = self.analyzer.extract_events(items)
        self.state.update_known(events)
        known = self.state.data.get("known", {}) if isinstance(self.state.data, dict) else {}
        return self.generator.generate(now=now, user_name=user_name, topics=topics, events=events, known=known)

    def _suggest_B(self, user_name: str, default_question: str, mem_text: str, draft_text: str) -> Optional[str]:
        if not callable(self.llm_fn):
            return None

        mem_text = _clamp_text(mem_text or "", self.max_mem_chars)
        draft_text = _clamp_text(draft_text or "", self.max_draft_chars)
        tod = _time_of_day(_now_local())

        prompt = (
            "You are CTXQ. Improve the user question. Constraints: <=220 chars, time-of-day appropriate, not intrusive.\n"
            f"TimeOfDay: {tod}\n"
            f"User: {user_name}\n"
            f"DraftQuestion: {default_question}\n\n"
            f"CompressedMemory:\n{mem_text}\n\n"
            f"CompressedDraft:\n{draft_text}\n\n"
            "Output ONLY the question in one line."
        )
        try:
            out = str(self.llm_fn(prompt) or "").strip()
            out = re.sub(r"\s+", " ", out).strip()
            if len(out) < 10:
                return None
            if len(out) > 240:
                out = out[:237] + "..."
            return out
        except Exception:
            return None

    def suggest_question(
        self,
        default_question: str,
        user_name: str = "Owner",
        mem_text: str = "",
        draft_text: str = "",
    ) -> str:
        default_question = (default_question or "").strip()
        slot = (os.getenv("ESTER_CTXQ_SLOT", "A") or "A").strip().upper()
        now_ts = int(time.time())

        sugA = self._suggest_A(user_name=user_name)
        candidate = sugA.question.strip()

        if slot == "B":
            outB = self._suggest_B(
                user_name=user_name,
                default_question=candidate or default_question,
                mem_text=mem_text,
                draft_text=draft_text,
            )
            if outB:
                candidate = outB.strip()

        if candidate and self.state.can_ask(candidate, now_ts=now_ts):
            self.state.mark_asked(candidate, now_ts=now_ts)
            return candidate

        if default_question and self.state.can_ask(default_question, now_ts=now_ts):
            self.state.mark_asked(default_question, now_ts=now_ts)
            return default_question

        return default_question