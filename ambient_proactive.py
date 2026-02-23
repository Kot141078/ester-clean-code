# -*- coding: utf-8 -*-
from __future__ import annotations

"""
ambient_proactive.py — Ambient‑prosloyka (proactive) dlya redkikh korotkikh «idey» v Telegram.

Klyuchevaya pravka pod tvoy simptom:
- iskhodnik delal `from initiatives import choose_by_emotions`, no funktsiya mozhet otsutstvovat
  ili lezhat po drugomu puti (initsiativy kak paket, a ne modul).
- teper import ustoychivyy (neskolko kandidatov), a esli funktsii vse ravno net —
  vklyuchaetsya lokalnyy fallback chooser, chtoby modul NE padal pri importe.

Plyus uluchsheniya:
- AB/DRY‑RUN NEYMSPEYSNYY: AMBIENT_AB_MODE / ESTER_AMBIENT_AB_MODE / AB_MODE (fallback).
- mozhno podklyuchit vneshniy katalog idey cherez JSON: AMBIENT_IDEAS_FILE=...
- esli otpravka/people/chooser nedostupny — degradatsiya bez padeniy (log + molchanie).

ENV (vse optsionalno):
- AMBIENT_STATE_DIR=state
- AMBIENT_MIN_MINUTES=35
- AMBIENT_MAX_MINUTES=75
- AMBIENT_ANXIETY_THRESHOLD=0.65
- AMBIENT_LOOKBACK_LINES=50
- AMBIENT_PER_USER_COOLDOWN_MINUTES=180
- AMBIENT_MAX_PER_TICK=3
- AMBIENT_IDEAS_FILE=path/to/ideas.json
- ESTER_AMBIENT_AB_MODE=A|B  (ili AMBIENT_AB_MODE, AB_MODE fallback)

MOSTY:
- Yavnyy: kibernetika ↔ proaktivnost (nablyudenie → vybor → deystvie → zapis).
- Skrytyy #1: infoteoriya ↔ nadezhnost (chooser mozhet ischeznut, no sistema ne padaet).
- Skrytyy #2: prava ↔ bezopasnost (A/B zdes — pravo “pingovat” polzovatelya).
ZEMNOY ABZATs:
Eto kak otdelnaya knopka dvernogo zvonka s predokhranitelem: dazhe esli v dome vse “v B”,
zvonok mozhno ostavit v “A” (dry‑run), chtoby ne razbudit lyudey sluchaynym impulsom.
"""

import hashlib
import html
import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

# ---- optional imports (degrade gracefully) ----
try:
    from people import all_people  # type: ignore
except Exception:  # pragma: no cover
    all_people = None  # type: ignore[assignment]

try:
    from telegram_bot import send_text as tg_send  # type: ignore
except Exception:  # pragma: no cover
    tg_send = None  # type: ignore[assignment]


# ---- chooser import (robust) ----
ChooserFn = Callable[[Dict[str, float]], Iterable[Dict[str, Any]]]


def _read_ab_flag() -> str:
    """
    A/B dlya AMBIENT v poryadke prioriteta:
      1) ESTER_AMBIENT_AB_MODE
      2) AMBIENT_AB_MODE
      3) AB_MODE (globalnyy fallback)
    Vozvraschaet 'A' ili 'B'.
    """
    for key in ("ESTER_AMBIENT_AB_MODE", "AMBIENT_AB_MODE", "AB_MODE"):
        v = os.getenv(key)
        if v is None:
            continue
        v = str(v).strip().upper()
        if v in ("A", "B"):
            return v
    return "A"


def _try_import_chooser() -> Optional[ChooserFn]:
    """
    Probuem neskolko variantov, potomu chto u tebya initsiativy mogut byt:
    - initiatives.py (modul)
    - initiatives/ (paket) i funktsiya vnutri podpaketa
    - modules/initiatives/... (esli pereneseno v modules)
    """
    candidates = [
        ("initiatives", "choose_by_emotions"),
        ("initiatives.choose", "choose_by_emotions"),
        ("initiatives.chooser", "choose_by_emotions"),
        ("modules.initiatives", "choose_by_emotions"),
        ("modules.initiatives.choose", "choose_by_emotions"),
        ("modules.initiatives.chooser", "choose_by_emotions"),
    ]
    for mod_name, attr in candidates:
        try:
            m = __import__(mod_name, fromlist=[attr])
            fn = getattr(m, attr, None)
            if callable(fn):
                return fn  # type: ignore[return-value]
        except Exception:
            continue
    return None


def _load_ideas_file(path: str) -> List[Dict[str, Any]]:
    try:
        s = open(path, "r", encoding="utf-8-sig").read()
        obj = json.loads(s) if s.strip() else None
        if isinstance(obj, list):
            out = [x for x in obj if isinstance(x, dict)]
            return out
    except Exception:
        pass
    return []


def _fallback_choose_by_emotions(emotions: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Mini‑chooser: ne “umnyy”, no stabilnyy.
    Vozvraschaet spisok idey (dict: title/body/howto/tag).

    Idei — korotkie i “zemnye”: struktura → odin shag → proverka.
    """
    emo = emotions or {}
    def g(k: str) -> float:
        try:
            return float(emo.get(k, 0.0))
        except Exception:
            return 0.0

    anxiety = max(g("anxiety"), g("fear"), g("stress"))
    anger = g("anger")
    joy = g("joy")
    focus = g("focus")
    calm = g("calm")

    # bazovyy bank
    bank: List[Tuple[str, Dict[str, Any]]] = [
        ("focus", {"tag": "focus", "title": "Odin punkt → tri shaga", "body": "Vyberi odnu zadachu i razlozhi ee na 3 proveryaemykh shaga.", "howto": "Shag 1: vkhody, shag 2: deystvie, shag 3: test/kriteriy gotovo."}),
        ("calm", {"tag": "calm", "title": "Sniz shum", "body": "Snimi odin lishniy istochnik shuma/uvedomleniy na 2 chasa.", "howto": "Ostav tolko odin kanal i odin taymer."}),
        ("stress", {"tag": "stress", "title": "Sdelay malenkuyu pobedu", "body": "Sdelay 10‑minutnuyu zadachu, kotoraya umenshaet khaos.", "howto": "Naprimer: privesti odin katalog/skript v poryadok."}),
        ("joy", {"tag": "joy", "title": "Zafiksiruy uspekh", "body": "Zapishi odnoy strokoy: chto segodnya realno poluchilos.", "howto": "Eto povyshaet ustoychivost i snizhaet vnutrenniy shum."}),
        ("anger", {"tag": "anger", "title": "Okhladi reaktsiyu", "body": "Sformuliruy pretenziyu kak trebovanie k sisteme, a ne k lyudyam.", "howto": "Odna fraza: “Nuzhen kontrol X, inache Y lomaetsya”."}),
    ]

    # otsenka
    weights = {
        "focus": 0.8 * focus + 0.2 * (1.0 - anxiety),
        "calm": 0.8 * calm + 0.2 * (1.0 - anxiety),
        "stress": 0.7 * anxiety + 0.3 * (1.0 - calm),
        "joy": 0.9 * joy,
        "anger": 0.9 * anger,
    }

    # sortiruem bank po vesam kategorii (chtoby vernut neskolko kandidatov)
    bank_sorted = sorted(bank, key=lambda x: weights.get(x[0], 0.0), reverse=True)
    return [item for _, item in bank_sorted]


# chooser callable (resolved once, but can degrade to fallback)
_CHOOSER: ChooserFn | None = _try_import_chooser()


@dataclass(frozen=True)
class AmbientConfig:
    state_dir: str = "state"
    min_minutes: int = 35
    max_minutes: int = 75
    anxiety_threshold: float = 0.65
    lookback_lines: int = 50
    per_user_cooldown_minutes: int = 180
    max_per_tick: int = 3
    ideas_file: str = ""

    @staticmethod
    def from_env() -> "AmbientConfig":
        def _env_int(name: str, default: int) -> int:
            v = os.environ.get(name)
            if v is None:
                return default
            try:
                return int(v)
            except Exception:
                return default

        def _env_float(name: str, default: float) -> float:
            v = os.environ.get(name)
            if v is None:
                return default
            try:
                return float(v)
            except Exception:
                return default

        state_dir = os.environ.get("AMBIENT_STATE_DIR", "state")
        min_minutes = _env_int("AMBIENT_MIN_MINUTES", 35)
        max_minutes = _env_int("AMBIENT_MAX_MINUTES", 75)
        if min_minutes < 1:
            min_minutes = 1
        if max_minutes < min_minutes:
            max_minutes = min_minutes

        ideas_file = os.environ.get("AMBIENT_IDEAS_FILE", "").strip()

        return AmbientConfig(
            state_dir=state_dir,
            min_minutes=min_minutes,
            max_minutes=max_minutes,
            anxiety_threshold=_env_float("AMBIENT_ANXIETY_THRESHOLD", 0.65),
            lookback_lines=max(1, _env_int("AMBIENT_LOOKBACK_LINES", 50)),
            per_user_cooldown_minutes=max(0, _env_int("AMBIENT_PER_USER_COOLDOWN_MINUTES", 180)),
            max_per_tick=max(1, _env_int("AMBIENT_MAX_PER_TICK", 3)),
            ideas_file=ideas_file,
        )


def _safe_user_key(user: str) -> str:
    raw = (user or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


def _ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_json(path: str, obj: Dict[str, Any]) -> None:
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _tail_lines(path: str, n: int, block_size: int = 4096) -> List[str]:
    if n <= 0:
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            buf = b""
            pos = end
            lines: List[bytes] = []
            while pos > 0 and len(lines) <= n:
                step = min(block_size, pos)
                pos -= step
                f.seek(pos)
                chunk = f.read(step)
                buf = chunk + buf
                parts = buf.split(b"\n")
                buf = parts[0]
                lines = parts[1:] + lines
            if buf:
                lines = [buf] + lines
            tail = lines[-n:]
            return [ln.decode("utf-8", errors="replace").strip() for ln in tail if ln is not None]
    except Exception:
        return []


def _pick_hash(pick: Dict[str, Any]) -> str:
    title = str(pick.get("title", "")).strip()
    tag = str(pick.get("tag", "")).strip()
    body = str(pick.get("body", "")).strip()
    howto = str(pick.get("howto", "")).strip()
    raw = (title + "|" + tag + "|" + body + "|" + howto).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


class AmbientProactiveDaemon(threading.Thread):
    """Fonovyy potok, kotoryy izredka shlet «ideyu» v Telegram."""

    def __init__(
        self,
        memory_manager,
        providers,
        token: str,
        config: Optional[AmbientConfig] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        super().__init__(daemon=True, name="EsterAmbient")
        self.mm = memory_manager
        self.providers = providers
        self.token = token
        self.cfg = config or AmbientConfig.from_env()
        self._stop = stop_event or threading.Event()

        self.ab = _read_ab_flag()
        self._ideas_cache: List[Dict[str, Any]] = []

        _ensure_dir(self.cfg.state_dir)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        # nebolshoy dzhitter, chtoby raznye demony ne sinkhronizirovalis
        time.sleep(random.uniform(2.0, 15.0))
        next_fire = time.time() + self._next_interval_seconds()

        while not self._stop.is_set():
            now = time.time()
            if now >= next_fire:
                try:
                    self._tick()
                except Exception:
                    log.exception("Ambient tick failed")
                next_fire = time.time() + self._next_interval_seconds()

            sleep_s = max(0.5, min(60.0, next_fire - time.time()))
            self._stop.wait(timeout=sleep_s)

    def _next_interval_seconds(self) -> float:
        return random.uniform(self.cfg.min_minutes * 60.0, self.cfg.max_minutes * 60.0)

    def _tick(self) -> None:
        # perechityvaem AB kazhdyy tik — chtoby mozhno bylo pereklyuchat bez restarta
        self.ab = _read_ab_flag()

        if not callable(all_people) or not callable(tg_send):
            # net obyazatelnykh zavisimostey — molchim
            return

        people = all_people() or {}
        if not isinstance(people, dict) or not people:
            return

        eligible: List[tuple[str, Dict[str, Any], int, Dict[str, float], str]] = []
        for user, prof in people.items():
            if not isinstance(prof, dict):
                continue

            cid_raw = prof.get("chat_id")
            if cid_raw is None:
                continue
            try:
                cid = int(cid_raw)
            except Exception:
                continue
            if cid == -1:
                continue

            if not prof.get("consent") or prof.get("mute"):
                continue

            user_key = _safe_user_key(str(user))
            if not self._cooldown_ok(user_key):
                continue

            emotions = self._last_emotions(str(user))
            if emotions.get("anxiety", 0.0) > self.cfg.anxiety_threshold:
                continue

            eligible.append((str(user), prof, cid, emotions, user_key))

        if not eligible:
            return

        random.shuffle(eligible)
        sent = 0
        for user, prof, cid, emotions, user_key in eligible:
            if sent >= self.cfg.max_per_tick:
                break

            pick = self._pick_for_user(prof, emotions, user_key=user_key)
            if not pick:
                continue

            msg = self._format_message(user, pick)
            if not msg:
                continue

            try:
                if self.ab != "B":
                    # dry-run
                    log.info("[ambient] dry-run to user=%s cid=%s: %s", user, cid, msg)
                    self._mark_sent(user_key, pick)  # vse ravno dvigaem anti‑dubl, inache v dry-run budet “dolbit” odno i to zhe
                    sent += 1
                    continue

                tg_send(self.token, cid, msg)  # type: ignore[misc]
                self._mark_sent(user_key, pick)
                sent += 1
            except Exception:
                log.exception("Failed to send ambient idea to user=%s cid=%s", user, cid)

    def _format_message(self, user: str, pick: Dict[str, Any]) -> str:
        title = str(pick.get("title", "")).strip()
        body = str(pick.get("body", "")).strip()
        howto = str(pick.get("howto", "")).strip()

        if not title and not body:
            return ""

        u = html.escape(user)
        t = html.escape(title)
        b = html.escape(body)
        h = html.escape(howto)

        parts = [f"{u}, u menya est ideya: <b>{t}</b>"] if t else [f"{u}, u menya est ideya:"]
        if b:
            parts.append(b)
        if h:
            parts.append(f"👉 {h}")
        return "\n".join(parts)

    def _pick_for_user(self, prof: Dict[str, Any], emotions: Dict[str, float], user_key: str) -> Optional[Dict[str, Any]]:
        interests_raw = prof.get("interests", [])
        interests: List[str] = []
        if isinstance(interests_raw, (list, tuple)):
            interests = [str(x).strip().lower() for x in interests_raw if str(x).strip()]
        elif isinstance(interests_raw, str) and interests_raw.strip():
            interests = [interests_raw.strip().lower()]

        last = self._load_sent_state(user_key)
        last_pick_hash = str(last.get("last_pick_hash", ""))

        for cand in self._iter_candidates(emotions):
            if not isinstance(cand, dict):
                continue

            if last_pick_hash and _pick_hash(cand) == last_pick_hash:
                continue

            if not interests:
                return cand

            cand_tag = str(cand.get("tag", "")).lower()
            cand_title = str(cand.get("title", "")).lower()
            cand_body = str(cand.get("body", "")).lower()

            if any(tag and (tag in cand_tag or tag in cand_title or tag in cand_body) for tag in interests):
                return cand

        return None

    def _iter_candidates(self, emotions: Dict[str, float]) -> Iterable[Dict[str, Any]]:
        # 1) vneshniy fayl idey (esli zadan) — otdaem pervym, chtoby mozhno bylo upravlyat kontentom bez reliza koda
        if self.cfg.ideas_file:
            if not self._ideas_cache:
                self._ideas_cache = _load_ideas_file(self.cfg.ideas_file)
            if self._ideas_cache:
                return list(self._ideas_cache)

        # 2) chooser iz proekta, esli dostupen
        if callable(_CHOOSER):
            try:
                cands = _CHOOSER(emotions)  # type: ignore[misc]
                if cands is None:
                    return []
                if isinstance(cands, list):
                    return cands
                return list(cands)
            except Exception:
                log.exception("choose_by_emotions failed; fallback chooser used")

        # 3) fallback
        return _fallback_choose_by_emotions(emotions)

    def _notes_path(self, user: str) -> str:
        safe = (user or "").replace("..", "_")
        safe = safe.replace("/", "_").replace("\\", "_")
        return os.path.join(self.cfg.state_dir, f"notes_{safe}.jsonl")

    def _sent_state_path(self, user_key: str) -> str:
        return os.path.join(self.cfg.state_dir, f"ambient_sent_{user_key}.json")

    def _last_emotions(self, user: str) -> Dict[str, float]:
        path = self._notes_path(user)
        lines = _tail_lines(path, self.cfg.lookback_lines)
        for ln in reversed(lines):
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            emo = rec.get("emotions") or {}
            if isinstance(emo, dict) and emo:
                out: Dict[str, float] = {}
                for k, v in emo.items():
                    try:
                        out[str(k)] = float(v)
                    except Exception:
                        continue
                return out
        return {}

    def _load_sent_state(self, user_key: str) -> Dict[str, Any]:
        return _load_json(self._sent_state_path(user_key))

    def _cooldown_ok(self, user_key: str) -> bool:
        if self.cfg.per_user_cooldown_minutes <= 0:
            return True
        st = self._load_sent_state(user_key)
        last_ts = st.get("last_sent_ts")
        try:
            last_ts_f = float(last_ts)
        except Exception:
            return True
        return (time.time() - last_ts_f) >= (self.cfg.per_user_cooldown_minutes * 60.0)

    def _mark_sent(self, user_key: str, pick: Dict[str, Any]) -> None:
        st = {"last_sent_ts": time.time(), "last_pick_hash": _pick_hash(pick)}
        _save_json(self._sent_state_path(user_key), st)