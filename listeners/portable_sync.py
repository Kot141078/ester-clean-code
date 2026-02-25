# -*- coding: utf-8 -*-
"""listeners/portable_sync.py - fonovye “dotyagivaniya” portable ot pirov i avto-obnaruzhenie portable-USB.

This modul obedinyaet dve funktsii:
1) P2P Sync:
   - V rezhime A: indeksatsiya + publikatsiya offer (bez zagruzki blokov).
   - V rezhime B: + pull nedostayuschikh blokov u pirov v lokalnuyu tsel.

2) USB Auto-detection:
   - V rezhime A: only log/status (JSON), bez deystviy.
   - V rezhime B: pri nalichii portable-nositelya mozhet primenit resursy (optsionalno, env-flag).

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): zamknutyy tsikl “nablyudat → predlozhit → sinkhronizirovat.”
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): CAS + kheshi → tochnaya dozagruzka bez “tyanut vse zanovo”.
- Skrytyy 2 (Anatomiya ↔ Inzheneriya): kak proverka refleksa — stimul (USB/peer) → latentnost → otvet.

Zemnoy abzats:
Eto “dezhurnyy mekhanik” v odnom litse: regulyarno obkhodit sklad (lokalnye bloki), sveryaet s sosedyami
(piry) i otmechaet v zhurnale, kogda priekhal novyy instrumentalnyy yaschik (portable-USB). Esli pitanie
proselo, disk "podumal", set chikhnula - status JSON pozvolyaet uvidet, where imenno tsep tormozit,
ne gadaya na kofeynoy gusche.

# c=a+b"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# --- P2P Sync imports ---
from modules.replica.portable_sync_settings import load_sync_settings  # type: ignore
from modules.replica.portable_sync import index_current, pull_from_peer, set_offer  # type: ignore

# --- USB Auto-detection imports ---
from modules.portable.env import detect_portable_root  # type: ignore
from modules.portable.overlay import apply_lmstudio_resources  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
STATUS_FILE = STATE_DIR / "portable" / "status.json"
LOCK_FILE = STATE_DIR / "portable" / "portable_sync.lock"


# -------------------------
# Utility
# -------------------------

def _now_ts() -> int:
    return int(time.time())


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding=encoding, newline="\n")
    tmp.replace(path)


def _write_status(d: Dict[str, Any]) -> None:
    """Pishet status v JSON (atomarno, UTF-8)."""
    payload = json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True)
    _atomic_write_text(STATUS_FILE, payload, encoding="utf-8")


def _acquire_lock(stale_sec: int = 600) -> bool:
    """A simple onion file to avoid running two instances in parallel."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = _now_ts()
    try:
        if LOCK_FILE.exists():
            age = now - int(LOCK_FILE.stat().st_mtime)
            if age > max(1, int(stale_sec)):
                try:
                    LOCK_FILE.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"pid": os.getpid(), "ts": now}, ensure_ascii=False))
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def _release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


@dataclass
class _LoopCfg:
    loop: bool
    stop: threading.Event


# -------------------------
# P2P Sync
# -------------------------

def _p2p_once(cfg: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    man = index_current(cfg["base_dir"], cfg["cas_dir"], cfg["block_mb"])
    set_offer(man)
    t1 = time.perf_counter()
    return {"ok": True, "indexed": True, "latency_s": max(0.0, t1 - t0), "manifest": man}


def _p2p_pull(cfg: Dict[str, Any]) -> Dict[str, Any]:
    target = str(Path(cfg["base_dir"]).expanduser() / "replica" / "from_peer")
    peers = cfg.get("peers") or []
    token = cfg.get("token", "")

    pulls = []
    ok_any = False
    for peer in peers:
        try:
            rep = pull_from_peer(peer, cfg["cas_dir"], target, token=token)
            ok = bool(rep.get("ok"))
            ok_any = ok_any or ok
            pulls.append({"peer": peer, "ok": ok, "rep": rep})
        except Exception as e:  # noqa: BLE001
            pulls.append({"peer": peer, "ok": False, "error": f"{e.__class__.__name__}: {e}"})
    return {"ok": ok_any if peers else True, "pulled": True, "target": target, "pulls": pulls}


def run_p2p_sync(cfg: Dict[str, Any], loop_cfg: _LoopCfg, interval: int) -> None:
    print("[portable-sync][p2p] started", flush=True)
    while True:
        st: Dict[str, Any] = {
            "ts": _now_ts(),
            "ab": AB,
            "mode": "p2p",
            "cfg_enable": bool(cfg.get("enable")),
        }

        try:
            st["index"] = _p2p_once(cfg)
            if AB == "B":
                st["pull"] = _p2p_pull(cfg)
        except Exception as e:  # noqa: BLE001
            st["ok"] = False
            st["error"] = f"{e.__class__.__name__}: {e}"
        else:
            st["ok"] = True

        # We write the status as “last known state”
        try:
            _write_status(st)
        except Exception:
            pass

        if not loop_cfg.loop:
            break

        # Pauza
        if loop_cfg.stop.wait(timeout=max(60, int(interval))):
            break

    print("[portable-sync][p2p] stopped", flush=True)


# -------------------------
# USB detection
# -------------------------

def _usb_once(period_hint: int = 8) -> Dict[str, Any]:
    root = detect_portable_root(None)
    st: Dict[str, Any] = {
        "ts": _now_ts(),
        "ab": AB,
        "mode": "usb",
        "portable_root": str(root) if root else None,
        "period_hint_s": int(period_hint),
    }

    # In mode B, you can enable auto-use of resources (only if the flag is set)
    if root and AB == "B" and os.getenv("PORTABLE_AUTO_APPLY", "0") == "1":
        try:
            res = apply_lmstudio_resources(str(root))
            st["auto_apply"] = res
        except Exception as e:  # noqa: BLE001
            st["auto_apply"] = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    st["ok"] = True
    return st


def run_usb_detection(loop_cfg: _LoopCfg, period: int) -> None:
    print("[portable-sync][usb] started", flush=True)
    while True:
        try:
            st = _usb_once(period_hint=period)
        except Exception as e:  # noqa: BLE001
            st = {
                "ts": _now_ts(),
                "ab": AB,
                "mode": "usb",
                "ok": False,
                "error": f"{e.__class__.__name__}: {e}",
            }

        try:
            _write_status(st)
        except Exception:
            pass

        if not loop_cfg.loop:
            break

        if loop_cfg.stop.wait(timeout=max(2, int(period))):
            break

    print("[portable-sync][usb] stopped", flush=True)


# -------------------------
# CLI
# -------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester portable: P2P sync + USB detection listener")

    ap.add_argument(
        "--mode",
        choices=["p2p", "usb", "all"],
        default="all",
        help="Operating mode: p2p-sync, usb-detection or both.",
    )
    ap.add_argument("--loop", action="store_true", help="Run in an endless loop.")
    ap.add_argument(
        "--p2p-interval",
        type=int,
        default=0,
        help="P2P synchronization interval (sec). 0 = taken from settings (default).",
    )
    ap.add_argument("--usb-period", type=int, default=8, help="Period skanirovaniya USB (sek).")
    ap.add_argument("--lock-stale", type=int, default=600, help="After how many seconds will lock be considered obsolete?")

    args = ap.parse_args(argv)

    if not _acquire_lock(stale_sec=int(args.lock_stale)):
        print("[portable-sync] lock busy; exit", flush=True)
        return 0

    stop = threading.Event()
    loop_cfg = _LoopCfg(loop=bool(args.loop), stop=stop)

    try:
        # --- P2P Sync ---
        p2p_thread: Optional[threading.Thread] = None
        if args.mode in ("p2p", "all"):
            p2p_cfg = load_sync_settings()
            if not p2p_cfg.get("enable"):
                print("[portable-sync] p2p sync is disabled in settings", flush=True)
            else:
                p2p_interval = int(args.p2p_interval or p2p_cfg.get("interval", 600))
                if args.mode == "all" and args.loop:
                    p2p_thread = threading.Thread(
                        target=run_p2p_sync,
                        args=(p2p_cfg, loop_cfg, p2p_interval),
                        name="portable-p2p-sync",
                        daemon=True,
                    )
                    p2p_thread.start()
                else:
                    run_p2p_sync(p2p_cfg, loop_cfg, p2p_interval)

        # --- USB detection ---
        if args.mode in ("usb", "all"):
            run_usb_detection(loop_cfg, int(args.usb_period))

        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        stop.set()
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())