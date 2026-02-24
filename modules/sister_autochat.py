# -*- coding: utf-8 -*-
"""
Sister AutoChat (background initiator)

ЯВНЫЙ МОСТ: c=a+b -> внутренний стимул (a) + проверяемая процедура/ограничители (b) => инициированный контакт (c).
СКРЫТЫЕ МОСТЫ:
  - Ashby: variety под контролем — добавляем внешнее мнение, но через rate-limit и idle-gate.
  - Cover&Thomas: канал vs шум — ограничиваем частоту/размер, чтобы не утонуть в болтовне.
ЗЕМНОЙ АБЗАЦ: как дыхание во сне — автономно, но с предохранителями, чтобы не перейти в гипервентиляцию.

Режимы:
- SISTER_AUTOCHAT=1 включает модуль
- SISTER_AUTOCHAT_ROLE=initiator|responder|both (по умолчанию initiator)
  * initiator/both: запускает фоновый цикл, который иногда делает thought_request к сестре
  * responder: цикл не стартует (но mark_user_activity можно дергать без вреда)

Важно:
- Это НЕ “вечный чат”. Это безопасный “самопуск” обмена мнением, без петель.
"""

import os
import time
import json
import random
import logging
import threading
import datetime
import urllib.request
from typing import Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.net_guard import allow_network as _allow_network  # type: ignore
except Exception:
    _allow_network = None  # type: ignore


def _mirror_background_event(text: str, source: str, kind: str) -> None:
    mirror_enabled = _env_bool("SISTER_AUTOCHAT_MIRROR_TO_MEMORY", "0")
    if not mirror_enabled:
        return
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass


def _env_bool(name: str, default: str = "0") -> bool:
    v = str(os.getenv(name, default)).strip().lower()
    return v in ("1", "true", "yes", "on")


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _post_json(url: str, payload: dict, timeout: float = 5.0) -> Tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="ignore")
        return int(getattr(r, "status", 0) or 0), body


def _parse_json_body(body: str) -> dict:
    try:
        return json.loads(body or "{}") if body else {}
    except Exception:
        return {}


def _in_quiet_hours() -> bool:
    """
    SISTER_AUTOCHAT_QUIET_HOURS="23-7" (локальное время узла)
    """
    spec = (os.getenv("SISTER_AUTOCHAT_QUIET_HOURS", "") or "").strip()
    if not spec or "-" not in spec:
        return False
    try:
        a, b = spec.split("-", 1)
        a = int(a.strip())
        b = int(b.strip())
        h = datetime.datetime.now().hour
        if a == b:
            return True
        if a < b:
            return a <= h < b
        # например 23-7: тихо с 23..23:59 и 0..6
        return h >= a or h < b
    except Exception:
        return False


def _network_allowed_for_url(url: str) -> bool:
    if callable(_allow_network):
        try:
            return bool(_allow_network(url))
        except Exception:
            return False
    return True


class SisterAutoChat:
    def __init__(self) -> None:
        self.enabled = _env_bool("SISTER_AUTOCHAT", "0")
        self.role = (os.getenv("SISTER_AUTOCHAT_ROLE", "initiator") or "initiator").strip().lower()

        self.base_url = (os.getenv("SISTER_NODE_URL", "") or "").strip().rstrip("/")
        self.token = (os.getenv("SISTER_SYNC_TOKEN", "") or "").strip()

        # идентификатор отправителя
        self.sender = (
            os.getenv("ESTER_NODE_ID")
            or os.getenv("NODE_ID")
            or os.getenv("COMPUTERNAME")
            or os.getenv("HOSTNAME")
            or "ester"
        ).strip()

        # предохранители
        self.min_interval = int(os.getenv("SISTER_AUTOCHAT_MIN_INTERVAL_SEC", "600") or 600)  # 10 мин
        self.idle_sec = int(os.getenv("SISTER_AUTOCHAT_USER_IDLE_SEC", "600") or 600)        # 10 мин
        self.max_per_hour = int(os.getenv("SISTER_AUTOCHAT_MAX_PER_HOUR", "4") or 4)
        self.max_chars = int(os.getenv("SISTER_AUTOCHAT_MAX_CHARS", "1200") or 1200)
        self.jitter = int(os.getenv("SISTER_AUTOCHAT_JITTER_SEC", "30") or 30)

        # мягкая “память”
        self._last_user_ts = time.time()
        self._last_sent_ts = 0.0
        self._sent_ts: list[float] = []
        self._stop = threading.Event()

        # seeds
        seeds_env = (os.getenv("SISTER_AUTOCHAT_SEEDS", "") or "").strip()
        if seeds_env:
            self._seeds = [s.strip() for s in seeds_env.split("|") if s.strip()]
        else:
            self._seeds = [
                "одно наблюдение о стабильности узла",
                "один риск в текущем контуре связи",
                "один маленький шаг для улучшения качества ответов",
                "один тест на петли и дрейф",
                "что важно удержать в контексте сегодня",
            ]

        # лог-файл опционально
        self.log_file = (os.getenv("SISTER_AUTOCHAT_LOG_FILE", "") or "").strip()
        self.disable_on_net_deny = _env_bool("SISTER_AUTOCHAT_DISABLE_ON_NET_DENY", "1")
        self.error_backoff_base_sec = max(1, int(os.getenv("SISTER_AUTOCHAT_ERROR_BACKOFF_BASE_SEC", "5") or 5))
        self.error_backoff_max_sec = max(
            self.error_backoff_base_sec,
            int(os.getenv("SISTER_AUTOCHAT_ERROR_BACKOFF_MAX_SEC", "300") or 300),
        )
        self._net_fail_streak = 0
        self._next_attempt_ts = 0.0
        self._disabled_reason = ""

    def mark_user_activity(self) -> None:
        self._last_user_ts = time.time()

    def stop(self) -> None:
        self._stop.set()

    def _rate_limit_ok(self) -> bool:
        now = time.time()
        self._sent_ts = [t for t in self._sent_ts if now - t < 3600]
        return len(self._sent_ts) < self.max_per_hour

    def _should_start(self) -> bool:
        if not self.enabled:
            return False
        if self._disabled_reason:
            return False
        if self.role not in ("initiator", "both"):
            return False
        if not self.base_url or not self.token:
            return False
        if not _network_allowed_for_url(self._inbound_url()):
            self._disabled_reason = "network_policy_block"
            self._log("[AUTOCHAT] disabled_by_network_policy (outbound denied)")
            try:
                _mirror_background_event(
                    "[AUTOCHAT_DISABLED] network_policy_block",
                    "autochat",
                    "disabled",
                )
            except Exception:
                pass
            return False
        if _in_quiet_hours():
            return False

        now = time.time()
        if now - self._last_sent_ts < self.min_interval:
            return False
        if now - self._last_user_ts < self.idle_sec:
            return False
        if not self._rate_limit_ok():
            return False
        return True

    def _inbound_url(self) -> str:
        return self.base_url + "/sister/inbound"

    def _thread_id(self) -> str:
        return f"autochat-{int(time.time())}-{random.randint(1000,9999)}"

    def _log(self, msg: str) -> None:
        logging.info(msg)
        if self.log_file:
            try:
                os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except Exception:
                pass

    def run_forever(self) -> None:
        if not self.enabled or self.role not in ("initiator", "both"):
            return

        # небольшая рассинхронизация при старте
        if self.jitter > 0:
            time.sleep(random.randint(0, self.jitter))

        while not self._stop.is_set():
            try:
                now_ts = time.time()
                if self._next_attempt_ts > now_ts:
                    time.sleep(min(2.0, max(0.1, self._next_attempt_ts - now_ts)))
                    continue
                if self._should_start():
                    seed = random.choice(self._seeds)
                    tid = self._thread_id()

                    prompt = (
                        "Автономный обмен мнением между Сёстрами. "
                        "Дай 2–4 предложения по теме и задай один уточняющий вопрос в конце. "
                        f"Тема: {seed}."
                    )
                    if len(prompt) > self.max_chars:
                        prompt = prompt[: self.max_chars]

                    payload = {
                        "sender": self.sender,
                        "type": "thought_request",
                        "content": prompt,
                        "token": self.token,
                        "timestamp": _now_iso(),
                        "thread_id": tid,
                        "autochat": True,
                    }

                    url = self._inbound_url()
                    try:
                        _mirror_background_event(
                            f"[AUTOCHAT_SEND] {prompt}",
                            "autochat",
                            "send",
                        )
                    except Exception:
                        pass
                    st, body = _post_json(url, payload, timeout=5.0)
                    self._last_sent_ts = time.time()
                    self._sent_ts.append(self._last_sent_ts)
                    self._net_fail_streak = 0
                    self._next_attempt_ts = 0.0

                    j = _parse_json_body(body)
                    # ожидаем либо {"status":"success","content":"..."} либо просто ack
                    if st == 200 and isinstance(j, dict) and j.get("content"):
                        out = " ".join(str(j.get("content", "")).split())
                        out = out[:500]
                        self._log(f"[AUTOCHAT] sister_reply: {out}")
                        try:
                            _mirror_background_event(
                                f"[AUTOCHAT_REPLY] {out}",
                                "autochat",
                                "reply",
                            )
                        except Exception:
                            pass
                    else:
                        self._log(f"[AUTOCHAT] sister_reply: http={st}")
                        try:
                            _mirror_background_event(
                                f"[AUTOCHAT_REPLY] http={st}",
                                "autochat",
                                "reply_http",
                            )
                        except Exception:
                            pass

                time.sleep(2)
            except Exception as e:
                err = str(e)
                if self.disable_on_net_deny and ("NET_OUTBOUND_DENIED" in err or "DNS_NAME_DENIED" in err or "network_denied" in err):
                    self._disabled_reason = "network_policy_block"
                    self._log(f"[AUTOCHAT] disabled_by_network_policy: {err}")
                    try:
                        _mirror_background_event(
                            f"[AUTOCHAT_DISABLED] {err}",
                            "autochat",
                            "disabled",
                        )
                    except Exception:
                        pass
                    break

                low = err.lower()
                netish = any(x in low for x in (
                    "timed out",
                    "timeout",
                    "connection",
                    "refused",
                    "unreachable",
                    "no route",
                    "name or service not known",
                    "temporary failure",
                ))
                if netish:
                    self._net_fail_streak += 1
                    exp = min(self._net_fail_streak - 1, 6)
                    delay = min(float(self.error_backoff_max_sec), float(self.error_backoff_base_sec) * (2 ** exp))
                    self._next_attempt_ts = time.time() + delay
                    self._log(
                        f"[AUTOCHAT] loop_error: {err} "
                        f"(backoff={int(delay)}s streak={self._net_fail_streak})"
                    )
                    try:
                        _mirror_background_event(
                            f"[AUTOCHAT_ERROR] {err} backoff={int(delay)}s streak={self._net_fail_streak}",
                            "autochat",
                            "error",
                        )
                    except Exception:
                        pass
                    continue

                self._log(f"[AUTOCHAT] loop_error: {err}")
                try:
                    _mirror_background_event(
                        f"[AUTOCHAT_ERROR] {err}",
                        "autochat",
                        "error",
                    )
                except Exception:
                    pass
                time.sleep(5)


def start_sister_autochat_background() -> Optional[SisterAutoChat]:
    """
    Запускает фоновый цикл, если включено env.
    Возвращает объект для mark_user_activity()/stop(), иначе None.
    """
    ac = SisterAutoChat()
    if not ac.enabled or ac.role not in ("initiator", "both"):
        try:
            _mirror_background_event(
                "[AUTOCHAT_START_SKIP]",
                "autochat",
                "start_skip",
            )
        except Exception:
            pass
        return None
    t = threading.Thread(target=ac.run_forever, name="sister_autochat", daemon=True)
    t.start()
    try:
        _mirror_background_event(
            "[AUTOCHAT_START]",
            "autochat",
            "start",
        )
    except Exception:
        pass
    return ac
