# -*- coding: utf-8 -*-
from __future__ import annotations

"""
modules/listeners/usb_dyn_driver.py — «umnaya» obertka dlya USB-agenta s adaptivnym intervalom.

Role:
- Zapuskat docherniy protsess: `python -m listeners.usb_zt_agent_v2 --loop --interval N`
- Periodicheski izmeryat pitanie/zaryad i pri izmeneniyakh perezapuskat agenta s novym N.
- (Optsionalno) Esli vklyuchen Zero-Click (ENV ESTER_USB_ZEROCLICK=1 ili settings.zeroclick==true i !locked),
  zapuskat watcher: `python -m listeners.usb_zero_click --interval <poll>` i sledit, chtoby on zhil.
- Bez vneshnikh zavisimostey, krossplatformenno, s akkuratnoy ostanovkoy.

CLI:
  python -m listeners.usb_dyn_driver [--mode eco|balanced|fast|off] [--min 2] [--max 60]
                                    [--ac-boost 0.5] [--poll 10] [--child-io inherit|devnull]

Istochniki parametrov (prioritet):
  1) CLI flagi (esli zadany)
  2) ENV: ESTER_USB_MODE / ESTER_USB_MIN / ESTER_USB_MAX / ESTER_USB_AC_BOOST / ESTER_USB_ZEROCLICK
  3) Konfig: modules.selfmanage.usb_tuning_state (ESTER_STATE_DIR/usb_tuning.json)
  4) Defolty: mode=balanced, min=3, max=45, ac_boost=0.5, poll=10

Mosty:
- Yavnyy: kibernetika ↔ orkestratsiya protsessov (nablyudenie→reshenie→deystvie→nablyudenie).
- Skrytyy 1: infoteoriya ↔ nadezhnost (resheniya po ogranichennym nablyudeniyam, bez «dogadok»).
- Skrytyy 2: praktika ↔ sovmestimost (ne trogaem iskhodnyy agent, tolko upravlyaem chastotoy).
Zemnoy abzats:
  Kak medsestra na obkhode: na seti chasche, na bataree ekonomnee. I prismatrivaet za «vtorym dezhurnym» (Zero-Click),
  esli tot naznachen na smenu.
"""

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from modules.selfmanage.power_sense import power_status  # type: ignore
from modules.selfmanage.usb_tuning_state import load_tuning  # type: ignore
from modules.usb.usb_trust_store import settings as trust_settings  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class Tuning:
    mode: str
    min_s: int
    max_s: int
    ac_boost: float
    poll: int
    child_io: str  # "inherit" | "devnull"


def _coalesce_cli_env_cfg(cli_val: Optional[Any], env_key: str, cfg: dict, cfg_key: str, default: Any) -> Any:
    """
    Pravilo: esli CLI znachenie «zadano» (ne None) — ispolzuem ego, inache ENV, inache cfg, inache default.
    Dlya int/float CLI my ispolzuem None-defolty, chtoby «0» ne schitalsya zadannym.
    """
    if cli_val is not None:
        return cli_val
    env_v = os.getenv(env_key)
    if env_v is not None and str(env_v).strip() != "":
        return env_v
    v = cfg.get(cfg_key)
    return default if v is None else v


def _resolve_tuning(args: argparse.Namespace) -> Tuning:
    cfg = load_tuning() or {}

    mode_raw = _coalesce_cli_env_cfg(args.mode, "ESTER_USB_MODE", cfg, "mode", "balanced")
    mode = str(mode_raw).lower().strip()
    if mode not in ("eco", "balanced", "fast", "off"):
        mode = "balanced"

    min_raw = _coalesce_cli_env_cfg(args.min_s, "ESTER_USB_MIN", cfg, "min_s", 3)
    max_raw = _coalesce_cli_env_cfg(args.max_s, "ESTER_USB_MAX", cfg, "max_s", 45)
    boost_raw = _coalesce_cli_env_cfg(args.ac_boost, "ESTER_USB_AC_BOOST", cfg, "ac_boost", 0.5)
    poll_raw = _coalesce_cli_env_cfg(args.poll, "ESTER_USB_POLL", cfg, "poll", 10)

    try:
        min_s = int(min_raw)
    except Exception:
        min_s = 3
    try:
        max_s = int(max_raw)
    except Exception:
        max_s = 45
    try:
        ac_boost = float(boost_raw)
    except Exception:
        ac_boost = 0.5
    try:
        poll = int(poll_raw)
    except Exception:
        poll = 10

    # Granitsy / sanity
    min_s = max(1, min_s)
    max_s = max(min_s + 1, max_s)
    ac_boost = max(0.1, min(1.0, ac_boost))
    poll = max(2, poll)

    child_io = (args.child_io or os.getenv("ESTER_USB_CHILD_IO") or "devnull").strip().lower()
    if child_io not in ("inherit", "devnull"):
        child_io = "devnull"

    return Tuning(mode=mode, min_s=min_s, max_s=max_s, ac_boost=ac_boost, poll=poll, child_io=child_io)


def _target_interval(t: Tuning, on_ac: Optional[bool], batt: Optional[int]) -> int:
    """
    Heuristics:
      eco:      AC -> mid; BAT -> max
      balanced: AC -> min*ac_boost; BAT -> mid..max (zavisit ot protsenta)
      fast:     AC -> min; BAT -> min*2..mid
      off:      fiksiruem mid (bez dinamiki)
    """
    mid = int((t.min_s + t.max_s) / 2)

    if t.mode == "off":
        return mid

    # esli ne znaem istochnik pitaniya — schitaem, chto ot seti (bezopasnee dlya reaktsii)
    if on_ac is None:
        on_ac = True

    batt = 100 if batt is None else max(0, min(100, int(batt)))

    if t.mode == "eco":
        return mid if on_ac else t.max_s

    if t.mode == "fast":
        if on_ac:
            return t.min_s
        # na bataree: rastem ot min*2 k mid pri padenii zaryada
        k = 1.0 + (100 - batt) / 100.0  # 1..2
        return int(min(mid, max(1, t.min_s * k)))

    # balanced
    if on_ac:
        return max(1, int(t.min_s * t.ac_boost))

    # na bataree: mezhdu mid i max v zavisimosti ot zaryada
    span = t.max_s - mid
    add = int(span * (1.0 - batt / 100.0))
    return mid + add


def _popen_stdio(child_io: str):
    if child_io == "inherit":
        return None, None, None  # znachit: nasleduem stdout/stderr
    return subprocess.DEVNULL, subprocess.DEVNULL, subprocess.DEVNULL


def _spawn_agent(interval: int, child_io: str) -> subprocess.Popen:
    argv = [sys.executable, "-m", "listeners.usb_zt_agent_v2", "--loop", "--interval", str(int(interval))]
    stdin, stdout, stderr = _popen_stdio(child_io)
    return subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr)


def _spawn_watcher(poll: int, child_io: str) -> subprocess.Popen:
    argv = [sys.executable, "-m", "listeners.usb_zero_click", "--interval", str(int(poll))]
    stdin, stdout, stderr = _popen_stdio(child_io)
    return subprocess.Popen(argv, stdin=stdin, stdout=stdout, stderr=stderr)


def _stop_proc(proc: Optional[subprocess.Popen], timeout_s: float = 5.0) -> None:
    if not proc:
        return
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout_s)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _restart_proc(proc: Optional[subprocess.Popen], spawn_func, arg: int, child_io: str) -> subprocess.Popen:
    _stop_proc(proc, timeout_s=5.0)
    return spawn_func(arg, child_io)


def _get_power_safe() -> Tuple[Optional[bool], Optional[int]]:
    """power_status() mozhet vybrasyvat; prevraschaem eto v (None, None)."""
    try:
        on_ac, batt = power_status()
        # batt mozhet byt float/str — normalizuem pozzhe
        return on_ac, batt  # type: ignore[return-value]
    except Exception:
        return None, None


def _changed_rel(old: int, new: int, rel: float = 0.2) -> bool:
    if old <= 0:
        return True
    return abs(old - new) / float(old) > float(rel)


def _zeroclick_should_run() -> bool:
    # ENV imeet prioritet: 1 -> on
    zc_env = (os.getenv("ESTER_USB_ZEROCLICK") or "0").strip() == "1"
    if zc_env:
        return True

    # konfig iz trust_store: zeroclick==true i !locked
    try:
        s = trust_settings() or {}
    except Exception:
        s = {}
    return bool(s.get("zeroclick")) and not bool(s.get("locked"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB smart driver")
    ap.add_argument("--mode", default=None, help="eco|balanced|fast|off")
    ap.add_argument("--min", dest="min_s", type=int, default=None, help="min interval seconds")
    ap.add_argument("--max", dest="max_s", type=int, default=None, help="max interval seconds")
    ap.add_argument("--ac-boost", dest="ac_boost", type=float, default=None, help="multiplier for AC -> min_s")
    ap.add_argument("--poll", dest="poll", type=int, default=None, help="power check period (sec)")
    ap.add_argument("--child-io", dest="child_io", default=None, help="inherit|devnull (default devnull)")
    args = ap.parse_args(argv)

    # startovaya nastroyka
    t = _resolve_tuning(args)

    # startovoe pitanie
    on_ac, batt = _get_power_safe()
    interval = _target_interval(t, on_ac, batt)

    agent = _spawn_agent(interval, t.child_io)
    watcher: Optional[subprocess.Popen] = None
    if _zeroclick_should_run():
        watcher = _spawn_watcher(t.poll, t.child_io)

    # vazhno: chtoby ne bylo «lishnego restarta» na pervom tsikle
    last_on_ac: Optional[bool] = on_ac
    last_interval: int = interval

    print(
        f"[usb_dyn_driver] start: mode={t.mode} ac={on_ac} batt={batt} "
        f"interval={interval} poll={t.poll} zc={'on' if watcher else 'off'} child_io={t.child_io}",
        flush=True,
    )

    try:
        while True:
            time.sleep(t.poll)

            # obnovlyaem tuning na letu (esli kto-to menyaet state/env) — no CLI, esli zadan, ostaetsya prioritetom
            t = _resolve_tuning(args)

            on_ac, batt = _get_power_safe()
            new_interval = _target_interval(t, on_ac, batt)

            # 1) sledim za agentom: esli umer — podnyat; esli interval silno pomenyalsya ili smenilsya istochnik — restart
            agent_dead = (agent.poll() is not None)
            need_restart = agent_dead or _changed_rel(last_interval, new_interval, rel=0.2) or (on_ac != last_on_ac)

            if need_restart:
                interval = new_interval
                agent = _restart_proc(agent, _spawn_agent, interval, t.child_io)
                last_interval = interval
                last_on_ac = on_ac
                print(f"[usb_dyn_driver] restart-agent: ac={on_ac} batt={batt} interval={interval}", flush=True)

            # 2) sledim za watcher (Zero-Click)
            zc_should_run = _zeroclick_should_run()
            if zc_should_run:
                if watcher is None or watcher.poll() is not None:
                    action = "start" if watcher is None else "restart"
                    watcher = _restart_proc(watcher, _spawn_watcher, t.poll, t.child_io)
                    print(f"[usb_dyn_driver] {action}-watcher", flush=True)
            else:
                if watcher and watcher.poll() is None:
                    _stop_proc(watcher, timeout_s=3.0)
                    watcher = None
                    print("[usb_dyn_driver] stop-watcher", flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        print("[usb_dyn_driver] shutting down...", flush=True)
        _stop_proc(agent, timeout_s=3.0)
        _stop_proc(watcher, timeout_s=3.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())