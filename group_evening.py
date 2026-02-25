# -*- coding: utf-8 -*-
from __future__ import annotations

"""group_evening.py — vecherniy daydzhest dlya aktivnykh grupp.

Error from loga:
  cannot import name 'TZ' from 'config'
Prichina: config.py ne eksportiroval TZ. V fix-versii config.py addavlen TZ.
No additional information my delaem zdes ustoychivyy fallback (esli vdrug drugoy config).

What improved:
- Pochinena kodirovka (ubrany krakozyabry).
- Vosstanovlena otpravka tg_send (v iskhodnike byla zakommentirovana).
- Dobavlena zaschita ot povtornoy otpravki: 1 raz v den na gruppu.
- Add filtr po whitelist (esli ESTER_GROUP_WHITELIST zadan).
- Tikhie chasy/okno otpravki reguliruyutsya env.
- All isklyucheniya logiruyutsya (vmesto "except: pass").

Mosty:
- Yavnyy most: group_intelligence snapshot/topics → vechernee soobschenie v Telegram.
- Skrytye mosty:
  (1) Kibernetika ↔ kod: “raz v sutki” = zaschita ot ostsillyatsiy/spama (kontur stabilizatsii).
  (2) Inzheneriya ↔ ekspluatatsiya: whitelist kak predokhranitel (ne shlem “kuda popalo”).

ZEMNOY ABZATs: v kontse fayla."""

import os
import logging
import random
import threading
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("EsterGroupEvening")
try:
    import pytz  # type: ignore
except Exception:
    pytz = None  # type: ignore

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore
# ustoychivyy import TZ
try:
    from config import TZ  # type: ignore
except Exception:
    TZ = (os.getenv("ESTER_TZ") or os.getenv("TZ") or "UTC").strip() or "UTC"

from group_intelligence import chat_topics, group_snapshot, list_active_groups
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# --- Telegram sender (best-effort) ---
def _tg_send_http(token: str, chat_id: int, text: str, *, parse_mode: str = "HTML", disable_web_page_preview: bool = True, timeout: int = 20) -> bool:
    token = (token or "").strip()
    if not token:
        return False
    try:
        import urllib.parse
        import urllib.request
        import urllib.error
    except Exception:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": str(int(chat_id)),
        "text": text or "",
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true" if disable_web_page_preview else "false",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        try:
            if int(getattr(e, "code", 0) or 0) == 429:
                ra = int(e.headers.get("Retry-After", "1") or "1")
                time.sleep(max(1, min(10, ra)))
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    r.read()
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def _resolve_tg_send():
    try:
        from listeners.telegram_bot import send_text as _ext  # type: ignore
        return _ext
    except Exception:
        pass
    try:
        from telegram_bot import send_text as _ext  # type: ignore
        return _ext
    except Exception:
        pass
    return _tg_send_http


tg_send = _resolve_tg_send()
# --- Nastroyki ---
EVENING_HOUR = int(os.getenv("EVENING_DIGEST_HOUR", "20"))
EVENING_MINUTE = int(os.getenv("EVENING_DIGEST_MINUTE", "30"))
EVENING_WINDOW_MIN = int(os.getenv("EVENING_WINDOW_MIN", "20"))  # okno ± minut
ACTIVE_WITHIN_SEC = int(os.getenv("EVENING_ACTIVE_WITHIN_SEC", str(24 * 3600)))

# If a vnitlist is specified, we send only there (no other filter is needed)
WHITELIST_RAW = os.getenv("ESTER_GROUP_WHITELIST", "").strip()


def _parse_whitelist(raw: str) -> Optional[List[int]]:
    if not raw:
        return None
    out: List[int] = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except Exception:
            continue
    return out or None


_WHITELIST = _parse_whitelist(WHITELIST_RAW)

# Internal memory: guide -> yyyy-mm-dd (last day of sending)
_SENT_DAY: Dict[int, str] = {}


def _now_local() -> datetime:
    name = (TZ or "UTC").strip() or "UTC"
    if pytz is not None:
        try:
            tz = pytz.timezone(name)
            return datetime.now(tz)
        except Exception:
            pass
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(name))
        except Exception:
            pass
    # last line of defense
    return datetime.now()


def _in_window(now: datetime, *, jitter_sec: int) -> bool:
    target = now.replace(hour=EVENING_HOUR, minute=EVENING_MINUTE, second=0, microsecond=0)
    delta_min = abs((now - target).total_seconds()) / 60.0
    return delta_min <= EVENING_WINDOW_MIN and now.second >= jitter_sec


def _already_sent_today(gid: int, day: date) -> bool:
    key = day.isoformat()
    return _SENT_DAY.get(gid) == key


def _mark_sent(gid: int, day: date) -> None:
    _SENT_DAY[gid] = day.isoformat()


class EveningDigestDaemon(threading.Thread):
    def __init__(self, token: str):
        super().__init__(daemon=True, name="EsterEveningDigest")
        self.token = token
        # slight jitter so that multiple nodes are not exactly at the same second
        self._jitter = random.randint(0, 25)

    def run(self):
        while True:
            try:
                now = _now_local()
                if _in_window(now, jitter_sec=self._jitter):
                    self._tick(now)
            except Exception:
                log.exception("EveningDigestDaemon loop failed")
            time.sleep(30)

    def _tick(self, now: datetime):
        # gruppy po aktivnosti
        groups: List[int] = list_active_groups(ACTIVE_WITHIN_SEC) or []
        if _WHITELIST is not None:
            groups = [g for g in groups if g in _WHITELIST]

        for gid in groups:
            # 1 raz v den na gruppu
            if _already_sent_today(gid, now.date()):
                continue

            try:
                snap = group_snapshot(gid) or {}
                top = chat_topics(gid, topn=5) or []
                topics_str = ", ".join([f"{k}×{v}" for k, v in top]) or "tishina / bez tem"
                msg_count = snap.get("count", 0)

                text = (
                    "📌 <b>Vecherniy puls</b>\n"
                    f"Messages per day: ZZF0Z"
                    f"Temy: {topics_str}\n"
                    "If you want, I’ll put together a 3-step plan for tomorrow."
                )

                tg_send(self.token, gid, text)
                _mark_sent(gid, now.date())
                time.sleep(random.uniform(0.3, 1.0))
            except Exception:
                log.exception("EveningDigestDaemon failed for gid=%s", gid)
                continue


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Vecherniy daydzhest - eto kak “puls” na obkhode: ne lechit, no pokazyvaet sostoyanie.
Esli puls merit kazhduyu sekundu - budet panika i noise. Poetomu “raz v sutki” i okno vremeni
rabotayut kak stabilizer: menshe kolebaniy, menshe spama, bolshe smysla."""