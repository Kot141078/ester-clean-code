# -*- coding: utf-8 -*-
from __future__ import annotations

"""
GroupDigestDaemon — periodicheski shlet v whitelisted-gruppy daydzhest i myagkuyu “obschuyu initsiativu”.

Tekuschaya oshibka iz loga:
  cannot import name 'suggest_assignments' from 'group_intelligence'
Prichina: v group_intelligence funktsiya nazvana inache (ili ee pereimenovali), a v group_digest
stoit zhestkiy import `from group_intelligence import suggest_assignments`, kotoryy valit import modulya.

Ispravlenie:
  - Ubrali zhestkiy import i sdelali “lazy resolver”:
      1) pytaemsya importirovat group_intelligence
      2) ischem funktsiyu sredi kandidatov (suggest_assignments / suggest_group_assignments / ...)
      3) esli nichego ne nashli — rabotaem v rezhime “digest-only” (bez plana)

Rabotaet tolko esli:
  - ESTER_GROUP_MODE=all
  - chat_id gruppy est v ESTER_GROUP_WHITELIST (cherez zapyatuyu)

Optsionalnye nastroyki:
  - ESTER_GROUP_WHITELIST="-100123,-100456"
  - ESTER_GROUP_QUIET_HOURS="23,7"          # ne pisat s 23:00 do 07:00
  - ESTER_GROUP_PERIOD_MIN="120,240"        # interval mezhdu daydzhestami (minuty)
  - ESTER_GROUP_MAX_LEN="3500"              # limit dliny soobscheniya

Mosty (trebovanie):
  - Yavnyy most: group_intelligence → group_digest → Telegram (plan/rezyume prevraschayutsya v deystvie/soobschenie).
  - Skrytye mosty:
      (1) Kibernetika ↔ kod: “fail-open” rezhim — esli plan sloman, sistema ne padaet, a degradiruet myagko.
      (2) Inzheneriya ↔ gigiena: lazy import ubiraet khrupkost avtoloada (minimizatsiya tochek otkaza).

ZEMNOY ABZATs: v kontse fayla.
"""

import datetime as _dt
import html
import inspect
import logging
import os
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# --- Telegram sender (best-effort) ---
# Pytaemsya pereispolzovat suschestvuyuschuyu realizatsiyu, esli ona est.
# Esli importa net/lomaetsya — ukhodim na pryamoy HTTP-vyzov Telegram Bot API.
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
        # Telegram 429: Too Many Requests, Retry-After header
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
    # 1) listeners.telegram_bot.send_text
    try:
        from listeners.telegram_bot import send_text as _ext  # type: ignore
        return _ext
    except Exception:
        pass
    # 2) telegram_bot.send_text
    try:
        from telegram_bot import send_text as _ext  # type: ignore
        return _ext
    except Exception:
        pass
    # 3) fallback: HTTP
    return _tg_send_http


tg_send = _resolve_tg_send()
# Defolty (mozhno pereopredelyat cherez env)
QUIET_HOURS: Tuple[int, int] = (23, 7)     # ne pishem s 23 do 7 (lokalno)
PERIOD_MIN: Tuple[int, int] = (120, 240)   # randomnyy interval mezhdu daydzhestami (minuty)
MAX_LEN_DEFAULT = 3500                     # bezopasnyy potolok dlya teksta

log = logging.getLogger("EsterGroupDigest")


def _parse_int_pair(env_name: str, default: Tuple[int, int], lo: int, hi: int) -> Tuple[int, int]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    try:
        a_s, b_s = (x.strip() for x in raw.split(",", 1))
        a, b = int(a_s), int(b_s)
        a = max(lo, min(hi, a))
        b = max(lo, min(hi, b))
        return (a, b)
    except Exception:
        return default


def _groups_from_env() -> List[int]:
    raw = os.getenv("ESTER_GROUP_WHITELIST", "").strip()
    if not raw:
        return []
    res: List[int] = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            res.append(int(p))
        except Exception:
            continue
    seen = set()
    out: List[int] = []
    for gid in res:
        if gid in seen:
            continue
        seen.add(gid)
        out.append(gid)
    return out


def _is_group_mode_all() -> bool:
    return os.getenv("ESTER_GROUP_MODE", "mention").strip().lower() == "all"


def _local_hour_now() -> int:
    return _dt.datetime.now().astimezone().hour


def _in_quiet_hours(hour: int, quiet: Tuple[int, int]) -> bool:
    q0, q1 = quiet
    if q0 == q1:
        return False
    if q0 < q1:
        return q0 <= hour < q1
    return hour >= q0 or hour < q1


def _clamp_message(text: str, max_len: int) -> str:
    if max_len <= 0:
        return text
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 1)] + "…"


def _resolve_suggest_fn() -> Optional[Callable[..., Any]]:
    """Ischet funktsiyu “suggest assignments” v group_intelligence bez padeniya importa."""
    try:
        import group_intelligence as gi  # type: ignore
    except Exception as e:
        log.warning("group_intelligence import failed: %s", e)
        return None

    candidates = [
        "suggest_assignments",
        "suggest_group_assignments",
        "suggest_assignments_for_group",
        "suggest",
        "build_assignments",
        "build_plan",
    ]
    for name in candidates:
        fn = getattr(gi, name, None)
        if callable(fn):
            return fn

    # esli pereimenovali sovsem — ne padaem
    log.warning("group_intelligence has no known suggest_* function (available: %s)", ",".join(sorted(set(
        [n for n in dir(gi) if ("suggest" in n.lower() or "assign" in n.lower())][:40]
    ))))
    return None


def _call_suggest(fn: Callable[..., Any], *, token: str, gid: int) -> Any:
    """Probuet vyzvat fn v raznykh signaturakh. Token peredaem tolko esli yavno trebuetsya parametrom."""
    # 1) prostye varianty bez tokena
    for args, kwargs in [
        ((gid,), {}),
        ((), {"chat_id": gid}),
        ((), {"group_id": gid}),
        ((str(gid),), {}),
        ((), {"chat_id": str(gid)}),
    ]:
        try:
            return fn(*args, **kwargs)
        except TypeError:
            pass

    # 2) esli v signature vidim token/bot_token — peredadim
    try:
        sig = inspect.signature(fn)
        kw: Dict[str, Any] = {}
        if "token" in sig.parameters:
            kw["token"] = token
        if "bot_token" in sig.parameters:
            kw["bot_token"] = token

        if "chat_id" in sig.parameters:
            kw["chat_id"] = gid
            return fn(**kw)
        if "group_id" in sig.parameters:
            kw["group_id"] = gid
            return fn(**kw)

        # posledniy shans: (token, gid)
        if kw:
            return fn(token, gid)
    except Exception:
        pass

    # 3) okonchatelno — pust caller obrabotaet
    return None


class GroupDigestDaemon(threading.Thread):
    def __init__(self, token: str):
        super().__init__(daemon=True, name="EsterGroupDigest")
        self.token = token
        self._next_run = time.monotonic() + 30.0

        self._quiet_hours = _parse_int_pair("ESTER_GROUP_QUIET_HOURS", QUIET_HOURS, 0, 23)
        self._period_min = _parse_int_pair("ESTER_GROUP_PERIOD_MIN", PERIOD_MIN, 1, 24 * 60)
        try:
            self._max_len = int(os.getenv("ESTER_GROUP_MAX_LEN", str(MAX_LEN_DEFAULT)).strip())
        except Exception:
            self._max_len = MAX_LEN_DEFAULT

        # resolve once (cheap), but if group_intelligence hot-reloads — mozhno pereklyuchit na per-tick
        self._suggest_fn = _resolve_suggest_fn()

    def run(self) -> None:
        while True:
            try:
                self._tick()
            except Exception:
                log.exception("GroupDigestDaemon tick crashed")
            time.sleep(15)

    def _tick(self) -> None:
        now_m = time.monotonic()
        if now_m < self._next_run:
            return

        interval_min = random.randint(*self._period_min)
        self._next_run = now_m + float(60 * interval_min)

        if not _is_group_mode_all():
            return
        if _in_quiet_hours(_local_hour_now(), self._quiet_hours):
            return

        groups = _groups_from_env()
        if not groups:
            return

        # esli funktsiya poyavilas posle starta — poprobuem podtyanut
        if self._suggest_fn is None:
            self._suggest_fn = _resolve_suggest_fn()

        for gid in groups:
            try:
                self._send_digest(gid)
                time.sleep(random.uniform(0.3, 1.2))
            except Exception:
                log.exception("Failed to send digest to gid=%s", gid)

    def _send_digest(self, gid: int) -> None:
        sug: Dict[str, Any] = {}
        if self._suggest_fn is not None:
            try:
                r = _call_suggest(self._suggest_fn, token=self.token, gid=gid)
                if isinstance(r, dict):
                    sug = r
            except Exception:
                log.debug("suggest function failed; fallback to empty plan", exc_info=True)

        s: Dict[str, Any] = (sug.get("summary") or {}) if isinstance(sug, dict) else {}
        plan = sug.get("plan") if isinstance(sug, dict) else None

        head = "🧭 Nebolshoe rezyume po chatu"

        top_participants = s.get("top_participants") or []
        top_themes = s.get("top_themes") or []

        people = ", ".join(f"{n}×{c}" for n, c in top_participants) if top_participants else "—"
        themes = ", ".join(f"{t}×{c}" for t, c in top_themes) if top_themes else "—"

        emo = s.get("avg_emotions") or {}
        try:
            interest = int(100 * float(emo.get("interest", 0) or 0))
        except Exception:
            interest = 0
        try:
            anxiety = int(100 * float(emo.get("anxiety", 0) or 0))
        except Exception:
            anxiety = 0

        lines = [
            head,
            f"Lidery: {people}",
            f"Temy: {themes}",
            f"Emotsii: interest {interest}% | anxiety {anxiety}%",
        ]
        text = "\n".join(lines)

        if isinstance(plan, list) and plan:
            p0 = plan[0] if isinstance(plan[0], dict) else {}
            title = html.escape(str(p0.get("title", "")).strip())
            body = html.escape(str(p0.get("body", "")).strip())
            howto = html.escape(str(p0.get("howto", "")).strip())

            extra = "\n"
            if title:
                extra += f"\nIdeya: <b>{title}</b>"
            if body:
                extra += f"\n{body}"
            if howto:
                extra += f"\n👉 {howto}"
            text += extra

        text = _clamp_message(text, self._max_len)
        tg_send(self.token, gid, text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not tok:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN")
    d = GroupDigestDaemon(tok)
    d.start()
    while True:
        time.sleep(3600)


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Eto kak dispetcher v tsekhu: esli odna mashina (group_intelligence) vremenno “vstala”,
tsekh ne dolzhen vyklyuchatsya tselikom — on perekhodit v ruchnoy rezhim i prodolzhaet vydavat minimum.
Lazy import + degradatsiya bez padeniya — eto predokhranitel, kak avtomat v schitke:
on ne delaet sistemu umnee, no delaet ee zhivuchey.
"""