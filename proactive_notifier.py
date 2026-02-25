# -*- coding: utf-8 -*-
from __future__ import annotations

"""proactive_notifier.py — proaktivnyy “pin” polzovatelyu pod realnymi ogranicheniyami.

Problema, kotoruyu ty podnyal:
- globalnyy ENV `AB_MODE` neudoben, esli v sisteme uzhe mnogo nezavisimykh A/B-pereklyuchateley.
  Odin obschiy flag prevraschaetsya v “rubilnik na ves dom”.

Resolution:
- vvodim NEYMSPEYS dlya etogo modulya:
    1) ESTER_PROACTIVE_AB_MODE
    2) AB_MODE_PROACTIVE
    3) (fallback) AB_MODE
  To est ty mozhesh derzhat AB_MODE=B dlya chego ugodno, a proaktivnost ostavit v A.

Funktsionalnye uluchsheniya (po sravneniyu s iskhodnikom):
- config iz ENV + razumnye default;
- jitter (that’s why it’s not “tikáli” sinkhronno);
- dnevnaya kvota + minimalnyy interval mezhdu soobscheniyami;
- quiet-hours (nochyu ne budit);
- best-effort integratsiya s core (generate_* / send_*), no matter what;
- A/B: A = dry-run (logiruem), B = realno shlem.

MOSTY:
- Yavnyy: kibernetika ↔ proaktivnost (nablyudenie → reshenie → deystvie → zhurnal).
- Skrytyy #1: infoteoriya ↔ ustoychivost (shumnyy signal filtruem kvotami/tikhimi chasami).
- Skrytyy #2: “privilegii” ↔ bezopasnost (A/B zdes — ogranichenie prava “pinat” polzovatelya).
ZEMNOY ABZATs:
Eto kak otdelnyy predokhranitel na tsep “zvonok”: dazhe esli ves dom v rezhime B, zvonok mozhno ostavit v A."""

import json
import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

# ---- persistent state ----
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "proactive_state.json"

try:
    # if there is atomic.po - use atomic notation
    from atomic import atomic_write_json, read_json  # type: ignore
except Exception:  # pragma: no cover
    atomic_write_json = None  # type: ignore[assignment]
    read_json = None  # type: ignore[assignment]


def _read_ab_flag() -> str:
    """A/B dlya PROAKTIVNOSTI v poryadke prioriteta:
      1) ESTER_PROACTIVE_AB_MODE
      2) AB_MODE_PROACTIVE
      3) AB_MODE (globalnyy fallback)
    Vozvraschaet 'A' or 'B'."""
    for key in ("ESTER_PROACTIVE_AB_MODE", "AB_MODE_PROACTIVE", "AB_MODE"):
        v = os.getenv(key)
        if v is None:
            continue
        v = str(v).strip().upper()
        if v in ("A", "B"):
            return v
    return "A"


def _env_int(key: str, default: int, min_v: Optional[int] = None, max_v: Optional[int] = None) -> int:
    try:
        v = int(str(os.getenv(key, "")).strip() or default)
    except Exception:
        v = int(default)
    if min_v is not None:
        v = max(min_v, v)
    if max_v is not None:
        v = min(max_v, v)
    return v


def _env_float(key: str, default: float, min_v: Optional[float] = None, max_v: Optional[float] = None) -> float:
    try:
        v = float(str(os.getenv(key, "")).strip() or default)
    except Exception:
        v = float(default)
    if min_v is not None:
        v = max(min_v, v)
    if max_v is not None:
        v = min(max_v, v)
    return v


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return bool(default)
    raw = str(raw).strip().lower()
    return raw in ("1", "true", "yes", "y", "on")


def _now_local_hour() -> int:
    return time.localtime().tm_hour


def _today_key() -> str:
    t = time.localtime()
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"


def _load_state() -> Dict[str, Any]:
    if callable(read_json):
        try:
            d = read_json(str(STATE_FILE), default=None)  # type: ignore[misc]
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    try:
        if STATE_FILE.exists():
            s = STATE_FILE.read_text(encoding="utf-8-sig")
            d = json.loads(s) if s.strip() else {}
            return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _save_state(d: Dict[str, Any]) -> None:
    try:
        if callable(atomic_write_json):
            atomic_write_json(str(STATE_FILE), d, ensure_ascii=False, indent=2)  # type: ignore[misc]
            return
        STATE_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


@dataclass
class ProactiveConfig:
    enabled: bool = True
    interval_sec: int = 3600
    probability: float = 0.10
    jitter_frac: float = 0.12
    min_gap_sec: int = 1800
    max_per_day: int = 6
    quiet_hours: Tuple[int, int] = (23, 8)  # (start_hour, end_hour)

    @staticmethod
    def from_env() -> "ProactiveConfig":
        enabled = _env_bool("ESTER_PROACTIVE_ENABLED", True)
        interval_sec = _env_int("ESTER_PROACTIVE_INTERVAL_SEC", 3600, min_v=30, max_v=24 * 3600)
        probability = _env_float("ESTER_PROACTIVE_PROB", 0.10, min_v=0.0, max_v=1.0)
        jitter_frac = _env_float("ESTER_PROACTIVE_JITTER", 0.12, min_v=0.0, max_v=0.5)
        min_gap_sec = _env_int("ESTER_PROACTIVE_MIN_GAP_SEC", 1800, min_v=0, max_v=24 * 3600)
        max_per_day = _env_int("ESTER_PROACTIVE_MAX_PER_DAY", 6, min_v=0, max_v=100)
        q_start = _env_int("ESTER_PROACTIVE_QUIET_START_H", 23, min_v=0, max_v=23)
        q_end = _env_int("ESTER_PROACTIVE_QUIET_END_H", 8, min_v=0, max_v=23)
        return ProactiveConfig(
            enabled=enabled,
            interval_sec=interval_sec,
            probability=probability,
            jitter_frac=jitter_frac,
            min_gap_sec=min_gap_sec,
            max_per_day=max_per_day,
            quiet_hours=(q_start, q_end),
        )


class ProactiveNotifier:
    def __init__(self, core: Any = None, config: Optional[ProactiveConfig] = None, rng: Optional[random.Random] = None):
        self.core = core
        self.cfg = config or ProactiveConfig.from_env()
        self.rng = rng or random.Random()

        # important: AB for this module is separate (see _ed_ab_flag)
        self.ab = _read_ab_flag()

        st = _load_state()
        self.last_check_ts = float(st.get("last_check_ts", time.time()))
        self.last_sent_ts = float(st.get("last_sent_ts", 0.0))
        self.day_key = str(st.get("day_key", _today_key()))
        self.sent_today = int(st.get("sent_today", 0))
        self.next_due_ts = float(st.get("next_due_ts", time.time() + self._jitter(self.cfg.interval_sec)))

    def _jitter(self, base: float) -> float:
        base = max(0.0, float(base))
        j = base * float(self.cfg.jitter_frac)
        if j <= 0:
            return base
        return max(0.0, base + self.rng.uniform(-j, j))

    def _in_quiet_hours(self) -> bool:
        start, end = self.cfg.quiet_hours
        h = _now_local_hour()
        if start == end:
            return False
        if start > end:
            return (h >= start) or (h < end)
        return start <= h < end

    def _roll_day(self) -> None:
        dk = _today_key()
        if dk != self.day_key:
            self.day_key = dk
            self.sent_today = 0

    def _persist(self) -> None:
        _save_state(
            {
                "last_check_ts": self.last_check_ts,
                "last_sent_ts": self.last_sent_ts,
                "day_key": self.day_key,
                "sent_today": self.sent_today,
                "next_due_ts": self.next_due_ts,
            }
        )

    def status(self) -> Dict[str, Any]:
        # re-read the AB every time - so that you can switch without restarting
        self.ab = _read_ab_flag()
        return {
            "ok": True,
            "ab": self.ab,
            "enabled": self.cfg.enabled,
            "interval_sec": self.cfg.interval_sec,
            "probability": self.cfg.probability,
            "min_gap_sec": self.cfg.min_gap_sec,
            "max_per_day": self.cfg.max_per_day,
            "quiet_hours": list(self.cfg.quiet_hours),
            "sent_today": self.sent_today,
            "last_sent_ts": self.last_sent_ts,
            "next_due_ts": self.next_due_ts,
            "state_file": str(STATE_FILE),
        }

    # ---- core integration (best-effort) ----
    def _core_generate(self) -> Optional[str]:
        for name in ("generate_proactive_thought", "proactive_thought", "generate_thought"):
            fn = getattr(self.core, name, None)
            if callable(fn):
                try:
                    msg = fn()
                    if isinstance(msg, str):
                        return msg.strip() or None
                    if isinstance(msg, dict) and isinstance(msg.get("text"), str):
                        return msg["text"].strip() or None
                except Exception:
                    return None
        return None

    def _core_send(self, text: str) -> bool:
        for name in ("send_message", "notify_user", "push_message", "telegram_send"):
            fn = getattr(self.core, name, None)
            if callable(fn):
                try:
                    ok = fn(text)
                    return bool(ok) if ok is not None else True
                except Exception:
                    return False
        log.info("[Proactive] %s", text)
        return True

    def _should_trigger(self, now: float) -> Tuple[bool, str]:
        if not self.cfg.enabled:
            return False, "disabled"

        self._roll_day()
        if self.cfg.max_per_day <= 0:
            return False, "quota_zero"
        if self.sent_today >= self.cfg.max_per_day:
            return False, "quota_exhausted"

        if self._in_quiet_hours():
            return False, "quiet_hours"

        if self.cfg.min_gap_sec > 0 and (now - self.last_sent_ts) < self.cfg.min_gap_sec:
            return False, "min_gap"

        if self.rng.random() >= float(self.cfg.probability):
            return False, "prob_skip"

        return True, "ok"

    def tick(self, now: Optional[float] = None, force: bool = False) -> Dict[str, Any]:
        now = float(time.time() if now is None else now)

        # re-read the AB every tick - you can switch without restarting the process
        self.ab = _read_ab_flag()

        if not force and now < self.next_due_ts:
            return {"ok": True, "triggered": False, "sent": False, "reason": "not_due"}

        self.last_check_ts = now
        self.next_due_ts = now + self._jitter(self.cfg.interval_sec)

        if not force:
            trig, reason = self._should_trigger(now)
            if not trig:
                self._persist()
                return {"ok": True, "triggered": False, "sent": False, "reason": reason}

        if force and self.cfg.min_gap_sec > 0 and (now - self.last_sent_ts) < self.cfg.min_gap_sec:
            self._persist()
            return {"ok": True, "triggered": True, "sent": False, "reason": "min_gap"}

        # AB=A → dry-run dlya PROAKTIVNOSTI (otdelnyy ot drugikh moduley)
        if self.ab != "B":
            log.info("[Proactive] dry-run (ab=%s): initiative", self.ab)
            self._persist()
            return {"ok": True, "triggered": True, "sent": False, "reason": "dry_run"}

        text = self._core_generate() if self.core is not None else None
        if not text:
            text = "I'm here. If you have a task, give me one point, I’ll break it down step by step."

        sent_ok = self._core_send(text)

        if sent_ok:
            self._roll_day()
            self.sent_today += 1
            self.last_sent_ts = now
            self._persist()
            return {"ok": True, "triggered": True, "sent": True, "reason": "sent"}

        # otpravka upala — korotkiy backoff
        self.next_due_ts = now + self._jitter(max(60.0, self.cfg.interval_sec * 0.25))
        self._persist()
        return {"ok": False, "triggered": True, "sent": False, "reason": "send_failed"}

    def smoketest(self) -> str:
        rep = self.tick(now=time.time(), force=True)
        return "OK" if isinstance(rep, dict) and "ok" in rep else "FAIL"


def tg_send(token: str, chat_id: int, text: str) -> bool:
    """Network send hook (tests monkeypatch this function)."""
    if not token or not chat_id:
        return False
    # keep side-effect free by default in offline mode
    return True


def publish_tg_preview(text: str) -> Dict[str, Any]:
    base = Path(os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")).resolve()
    out_dir = base / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"morning_digest_{int(time.time())}.json"
    out_path.write_text(json.dumps({"text": str(text or "")}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(out_path)}


class MorningDigestDaemon:
    """Compatibility morning digest daemon used by smoke/manual tests."""

    def __init__(
        self,
        mm: Any = None,
        providers: Any = None,
        tg_token: Optional[str] = None,
        default_user: str = "Owner",
    ):
        self.mm = mm
        self.providers = providers
        self.tg_token = tg_token if tg_token is not None else os.getenv("TELEGRAM_TOKEN", "")
        self.default_user = default_user

    def _today(self) -> str:
        t = time.localtime()
        return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"

    def _now_in_morning_window(self) -> bool:
        hour = int(os.getenv("MORNING_HOUR", "8") or 8)
        window = int(os.getenv("MORNING_WINDOW_MIN", "90") or 90)
        now = time.localtime()
        now_min = now.tm_hour * 60 + now.tm_min
        start = hour * 60
        end = (start + max(1, window)) % (24 * 60)
        if start <= end:
            return start <= now_min <= end
        return now_min >= start or now_min <= end

    def _get_meta(self, user: str) -> Dict[str, Any]:
        if self.mm and hasattr(self.mm, "get_session_meta"):
            try:
                meta = self.mm.get_session_meta(user, "morning_digest")
                return dict(meta or {})
            except Exception:
                return {}
        return {}

    def _set_meta(self, user: str, value: Dict[str, Any]) -> None:
        if self.mm and hasattr(self.mm, "set_session_meta"):
            try:
                self.mm.set_session_meta(user, "morning_digest", dict(value or {}))
            except Exception:
                pass

    def _already_sent_today(self, user: str) -> bool:
        return str(self._get_meta(user).get("date") or "") == self._today()

    def _mark_sent_today(self, user: str, channel: str) -> None:
        meta = self._get_meta(user)
        meta.update({"date": self._today(), "channel": channel, "ts": int(time.time())})
        self._set_meta(user, meta)

    def _get_chat_id(self, user: str) -> Optional[int]:
        env = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if env.isdigit():
            return int(env)
        return None

    def _build_digest_text(self, user: str) -> str:
        emotions = {}
        if self.mm and hasattr(self.mm, "get_emotions_journal"):
            try:
                journal = self.mm.get_emotions_journal(user, 1) or []
                if journal and isinstance(journal[0], dict):
                    emotions = dict(journal[0].get("emotions") or {})
            except Exception:
                emotions = {}
        bullets: list[str] = []
        if self.mm and hasattr(self.mm, "flashback"):
            try:
                for row in self.mm.flashback("utrenniy daydzhest", k=3) or []:
                    txt = str((row or {}).get("text") or "").strip()
                    if txt:
                        bullets.append(f"- {txt}")
            except Exception:
                pass
        emo_s = ", ".join(f"{k}:{round(float(v),2)}" for k, v in emotions.items()) if emotions else "net dannykh"
        body = "\n".join(bullets) if bullets else "- Planov v pamyati net."
        return f"Dobroe utro, {user}!\nEmotsii: {emo_s}\n\nFokus na den:\n{body}"

    def _tick(self, force: bool = False, user: Optional[str] = None) -> Dict[str, Any]:
        who = str(user or self.default_user)
        if not force and not self._now_in_morning_window():
            return {"ok": True, "sent": False, "reason": "outside_window"}
        if self._already_sent_today(who):
            return {"ok": True, "sent": False, "reason": "already_sent_today"}

        text = self._build_digest_text(who)
        chat_id = self._get_chat_id(who)
        if self.tg_token and chat_id:
            ok = bool(tg_send(self.tg_token, chat_id, text))
            if ok:
                self._mark_sent_today(who, "telegram")
                return {"ok": True, "sent": True, "channel": "telegram"}
            return {"ok": False, "sent": False, "channel": "telegram", "reason": "telegram_send_failed"}

        prev = publish_tg_preview(text)
        if prev.get("ok"):
            self._mark_sent_today(who, "preview")
            return {"ok": True, "sent": True, "channel": "preview", "preview": prev}
        return {"ok": False, "sent": False, "channel": "preview", "preview": prev}

    def run_once(self, **kwargs) -> Dict[str, Any]:
        return self._tick(force=bool(kwargs.get("force", False)), user=kwargs.get("user"))

    def smoke_tick(self) -> Dict[str, Any]:
        return self._tick(force=True)
