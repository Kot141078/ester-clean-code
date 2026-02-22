# -*- coding: utf-8 -*-
from __future__ import annotations

"""
modules/selfmanage/watchdog.py — nablyudenie i avto‑remont servisov.

Pochemu etot modul kritichen:
- esli storozh ne rabotaet, lyuboy «tikhiy» sboy (upal vorker, zavisla BD, umer poller) prevraschaet sistemu v khrupkuyu korobku.

Dizayn:
- Service(name, check, restart) — registriruemye servisy;
- Watchdog.tick() — odin prokhod (mozhno zvat vruchnuyu);
- Watchdog.start() — fonovyy potok (podnimaetsya tolko yavno cherez start_watchdog()).

Nadezhnost:
- check/restart obernuty: isklyucheniya ne valyat tsikl;
- eksponentsialnyy backoff + nebolshoy jitter;
- «kanareechnaya» pereproverka pered restartom;
- otchet poslednego tika dostupen cherez watchdog.last_report().

ENV:
- SELF_WATCH_ENABLE=1|0      (default=1)
- SELF_WATCH_INTERVAL_MS=1500
- SELF_WATCH_BACKOFF_MAX_SEC=60
- SELF_WATCH_DRYRUN=0|1      (default=0) — logiruem restart, no ne vypolnyaem (dlya bezopasnogo vvoda)

MOSTY:
- Yavnyy: kibernetika ↔ orkestratsiya protsessov (nablyudenie → reshenie → deystvie → nablyudenie).
- Skrytyy #1: infoteoriya ↔ ustoychivost (my deystvuem po shumnym signalam, no cherez gisterezis/backoff).
- Skrytyy #2: inzheneriya otkazoustoychivosti ↔ «audit trail» (posledniy otchet khranitsya i dostupen).

ZEMNOY ABZATs:
Eto kak avtomat zaschity v schitke: on ne delaet dom umnee, no ne daet melkoy neispravnosti prevratitsya v pozhar.
"""

import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# --- health model (best-effort compatibility) ---
try:
    from modules.selfmanage.health import HealthStatus, _ok, _fail  # type: ignore
except Exception:  # pragma: no cover
    @dataclass
    class HealthStatus:  # minimal fallback
        name: str
        status: str = "fail"  # "ok" | "fail"
        took_ms: int = 0
        reason: str = ""

    def _ok(name: str, took_ms: int = 0, **_) -> HealthStatus:
        return HealthStatus(name=name, status="ok", took_ms=int(took_ms), reason="")

    def _fail(name: str, took_ms: int = 0, reason: str = "", **_) -> HealthStatus:
        return HealthStatus(name=name, status="fail", took_ms=int(took_ms), reason=str(reason or ""))


CheckFn = Callable[[], HealthStatus]
RestartFn = Callable[[], bool]

def _mirror_background_event(text: str, source: str, kind: str) -> None:
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


@dataclass
class Service:
    name: str
    check: CheckFn
    restart: RestartFn
    backoff: float = 1.5          # koeffitsient rosta
    cooldown_sec: float = 2.0     # bazovyy interval mezhdu popytkami
    max_backoff_sec: float = float(os.getenv("SELF_WATCH_BACKOFF_MAX_SEC", "60"))


class Watchdog:
    """
    Watchdog ne «ugadyvaet», a delaet prostye veschi:
    - proveryaet servis,
    - pereproveryaet (kanareyka),
    - esli plokho — restartuet,
    - esli restart ne pomogaet — uvelichivaet pauzu (backoff).
    """

    def __init__(self, services: List[Service], interval_ms: Optional[int] = None, dry_run: Optional[bool] = None):
        self.services = list(services or [])
        self.interval_ms = int(interval_ms or int(os.getenv("SELF_WATCH_INTERVAL_MS", "1500")))
        self.interval_ms = max(250, self.interval_ms)

        self.dry_run = bool(int(os.getenv("SELF_WATCH_DRYRUN", "0"))) if dry_run is None else bool(dry_run)

        # name -> state
        # next_at: kogda sleduyuschiy raz mozhno trogat servis
        # cur_backoff: tekuschaya pauza backoff
        # fails: podryad neuspekhov
        # last_reason: tekst posledney oshibki
        self.state: Dict[str, Dict[str, float | int | str]] = {}

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._last_report: List[HealthStatus] = []

    # ---- public introspection ----
    def is_running(self) -> bool:
        th = self._thread
        return bool(th and th.is_alive())

    def last_report(self) -> List[HealthStatus]:
        with self._lock:
            return list(self._last_report)

    def register(self, service: Service) -> None:
        """Dobavit servis (bez perezapuska potoka)."""
        if not isinstance(service, Service):
            return
        self.services.append(service)

    # ---- internal ----
    def _ensure(self, name: str) -> Dict[str, float | int | str]:
        st = self.state.get(name)
        if not st:
            st = {"next_at": 0.0, "cur_backoff": 0.0, "fails": 0, "last_reason": ""}
            self.state[name] = st
        return st

    def _safe_check(self, s: Service) -> HealthStatus:
        t0 = time.time()
        try:
            hs = s.check()
            if not isinstance(hs, HealthStatus):
                hs = _fail(s.name, took_ms=int((time.time() - t0) * 1000), reason="bad_health_status_type")
            else:
                hs.took_ms = int((time.time() - t0) * 1000)  # type: ignore[attr-defined]
            return hs
        except Exception as e:
            return _fail(s.name, took_ms=int((time.time() - t0) * 1000), reason=f"check_exc:{e}")

    def _safe_restart(self, s: Service) -> Tuple[bool, str]:
        if self.dry_run:
            return True, "dry_run"
        t0 = time.time()
        try:
            ok = bool(s.restart())
            took = int((time.time() - t0) * 1000)
            return ok, f"restart_{'ok' if ok else 'fail'}:{took}ms"
        except Exception as e:
            return False, f"restart_exc:{e}"

    def _jitter(self, base: float, frac: float = 0.12) -> float:
        # nebolshoy dzhitter, chtoby vse servisy ne «schelkali» sinkhronno
        j = base * frac
        return max(0.0, base + random.uniform(-j, j))

    # ---- core ----
    def tick(self) -> List[HealthStatus]:
        """Odin prokhod po vsem servisam; vozvraschaet statusy i sokhranyaet last_report()."""
        report: List[HealthStatus] = []
        for s in list(self.services):
            now = time.time()
            st = self._ensure(s.name)

            next_at = float(st.get("next_at", 0.0))  # type: ignore[arg-type]
            if next_at > now:
                continue

            # 1) check
            hs = self._safe_check(s)
            report.append(hs)

            if hs.status == "ok":
                st["cur_backoff"] = 0.0
                st["fails"] = 0
                st["last_reason"] = ""
                st["next_at"] = now + self._jitter(s.cooldown_sec)
                continue

            # 2) canary re-check (korotkaya pereproverka)
            self._stop.wait(0.05)
            hs2 = self._safe_check(s)
            report.append(hs2)

            if hs2.status == "ok":
                st["cur_backoff"] = 0.0
                st["fails"] = 0
                st["last_reason"] = ""
                st["next_at"] = time.time() + self._jitter(s.cooldown_sec)
                continue

            # 3) restart
            ok, reason = self._safe_restart(s)
            if ok:
                st["cur_backoff"] = 0.0
                st["fails"] = 0
                st["last_reason"] = ""
                st["next_at"] = time.time() + self._jitter(s.cooldown_sec)
                report.append(_ok(f"{s.name}:restart", took_ms=0))
                try:
                    _mirror_background_event(
                        f"[SELF_WATCH_RESTART_OK] {s.name}",
                        "self_watchdog",
                        "restart_ok",
                    )
                except Exception:
                    pass
            else:
                # uvelichivaem bek‑off
                cur = float(st.get("cur_backoff", 0.0)) or float(s.cooldown_sec)
                cur = max(float(s.cooldown_sec), cur)
                cur = min(cur * float(s.backoff), float(s.max_backoff_sec))
                cur = self._jitter(cur)

                st["cur_backoff"] = cur
                st["fails"] = int(st.get("fails", 0)) + 1
                st["last_reason"] = str(reason)
                st["next_at"] = time.time() + cur

                report.append(_fail(f"{s.name}:restart", took_ms=0, reason=str(reason)))
                try:
                    _mirror_background_event(
                        f"[SELF_WATCH_RESTART_FAIL] {s.name} reason={reason}",
                        "self_watchdog",
                        "restart_fail",
                    )
                except Exception:
                    pass

        with self._lock:
            self._last_report = report
        return report

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                # ne daem «sobake» umeret ot isklyucheniya
                try:
                    _mirror_background_event(
                        "[SELF_WATCH_LOOP_ERROR]",
                        "self_watchdog",
                        "loop_error",
                    )
                except Exception:
                    pass
                pass
            self._stop.wait(self.interval_ms / 1000.0)

    def start(self) -> None:
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ester-watchdog", daemon=True)
        self._thread.start()
        try:
            _mirror_background_event(
                "[SELF_WATCH_START]",
                "self_watchdog",
                "start",
            )
        except Exception:
            pass

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        th = self._thread
        if th:
            th.join(timeout)
        try:
            _mirror_background_event(
                "[SELF_WATCH_STOP]",
                "self_watchdog",
                "stop",
            )
        except Exception:
            pass


# --------- gotovye servisy i zapusk ---------

def _check_db_service() -> HealthStatus:
    from modules.selfmanage.health import check_db  # type: ignore
    return check_db()  # type: ignore[return-value]


def _restart_db_service() -> bool:
    # SQLite reconnect proizoydet lenivo; prosto "potrogaem" soedinenie
    from modules.synergy.store import AssignmentStore  # type: ignore
    try:
        AssignmentStore.default().get_latest_plan("__health__")
        return True
    except Exception:
        return False


def _check_internal_service() -> HealthStatus:
    from modules.selfmanage.health import check_internal  # type: ignore
    return check_internal()  # type: ignore[return-value]


def _restart_internal_service() -> bool:
    # Peresozdadim vnutrennie keshi (poka — PlanCache)
    try:
        from modules.synergy.plan_cache import CACHE as C  # type: ignore
        C.put_plan("watchdog-reset", {"ok": True})
        return True
    except Exception:
        return False


def default_services() -> List[Service]:
    return [
        Service(name="db", check=_check_db_service, restart=_restart_db_service, cooldown_sec=3.0),
        Service(name="internal", check=_check_internal_service, restart=_restart_internal_service, cooldown_sec=2.0),
    ]


_WD: Optional[Watchdog] = None


def start_watchdog(services: Optional[List[Service]] = None, interval_ms: Optional[int] = None) -> Optional[Watchdog]:
    """
    Yavno zapustit fonovyy watchdog (esli SELF_WATCH_ENABLE=1).
    Esli watchdog uzhe sozdan, no potok umer/ostanovlen — podnimet snova.
    """
    if os.getenv("SELF_WATCH_ENABLE", "1") != "1":
        return None

    global _WD
    if _WD is None:
        _WD = Watchdog(services or default_services(), interval_ms=interval_ms)
        _WD.start()
        return _WD

    # uzhe est: obnovim interval, esli prosyat
    if interval_ms is not None:
        try:
            _WD.interval_ms = max(250, int(interval_ms))
        except Exception:
            pass

    if not _WD.is_running():
        _WD.start()

    return _WD


def stop_watchdog(timeout: float = 2.0) -> None:
    global _WD
    if _WD is None:
        return
    try:
        _WD.stop(timeout=timeout)
    except Exception:
        pass