# -*- coding: utf-8 -*-
"""
Sister AutoChat (background initiator)

YaVNYY MOST: c=a+b -> vnutrenniy stimul (a) + proveryaemaya protsedura/ogranichiteli (b) => initsiirovannyy kontakt (c).
SKRYTYE MOSTY:
  - Ashby: variety pod kontrolem — dobavlyaem vneshnee mnenie, no cherez rate-limit i idle-gate.
  - Cover&Thomas: kanal vs shum — ogranichivaem chastotu/razmer, chtoby ne utonut v boltovne.
ZEMNOY ABZATs: kak dykhanie vo sne — avtonomno, no s predokhranitelyami, chtoby ne pereyti v giperventilyatsiyu.

Rezhimy:
- SISTER_AUTOCHAT=1 vklyuchaet modul
- SISTER_AUTOCHAT_ROLE=initiator|responder|both (po umolchaniyu initiator)
  * initiator/both: zapuskaet fonovyy tsikl, kotoryy inogda delaet thought_request k sestre
  * responder: tsikl ne startuet (no mark_user_activity mozhno dergat bez vreda)

Vazhno:
- Eto NE “vechnyy chat”. Eto bezopasnyy “samopusk” obmena mneniem, bez petel.
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
    SISTER_AUTOCHAT_QUIET_HOURS="23-7" (lokalnoe vremya uzla)
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
        # naprimer 23-7: tikho s 23..23:59 i 0..6
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

        # identifikator otpravitelya
        self.sender = (
            os.getenv("ESTER_NODE_ID")
            or os.getenv("NODE_ID")
            or os.getenv("COMPUTERNAME")
            or os.getenv("HOSTNAME")
            or "ester"
        ).strip()

        # predokhraniteli
        self.min_interval = int(os.getenv("SISTER_AUTOCHAT_MIN_INTERVAL_SEC", "600") or 600)  # 10 min
        self.idle_sec = int(os.getenv("SISTER_AUTOCHAT_USER_IDLE_SEC", "600") or 600)        # 10 min
        self.max_per_hour = int(os.getenv("SISTER_AUTOCHAT_MAX_PER_HOUR", "4") or 4)
        self.max_chars = int(os.getenv("SISTER_AUTOCHAT_MAX_CHARS", "1200") or 1200)
        self.jitter = int(os.getenv("SISTER_AUTOCHAT_JITTER_SEC", "30") or 30)

        # myagkaya “pamyat”
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
                "odno nablyudenie o stabilnosti uzla",
                "odin risk v tekuschem konture svyazi",
                "odin malenkiy shag dlya uluchsheniya kachestva otvetov",
                "odin test na petli i dreyf",
                "chto vazhno uderzhat v kontekste segodnya",
            ]

        # log-fayl optsionalno
        self.log_file = (os.getenv("SISTER_AUTOCHAT_LOG_FILE", "") or "").strip()
        self.disable_on_net_deny = _env_bool("SISTER_AUTOCHAT_DISABLE_ON_NET_DENY", "1")
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

        # nebolshaya rassinkhronizatsiya pri starte
        if self.jitter > 0:
            time.sleep(random.randint(0, self.jitter))

        while not self._stop.is_set():
            try:
                if self._should_start():
                    seed = random.choice(self._seeds)
                    tid = self._thread_id()

                    prompt = (
                        "Avtonomnyy obmen mneniem mezhdu Sestrami. "
                        "Day 2–4 predlozheniya po teme i zaday odin utochnyayuschiy vopros v kontse. "
                        f"Tema: {seed}."
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

                    j = _parse_json_body(body)
                    # ozhidaem libo {"status":"success","content":"..."} libo prosto ack
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
    Zapuskaet fonovyy tsikl, esli vklyucheno env.
    Vozvraschaet obekt dlya mark_user_activity()/stop(), inache None.
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
