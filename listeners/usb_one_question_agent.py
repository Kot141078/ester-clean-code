# -*- coding: utf-8 -*-
"""
listeners/usb_one_question_agent.py — Zero-Touch USB agent (Windows + Linux + macOS).

Tsel: pri poyavlenii semnogo nositelya (USB) avtomaticheski:
  1) obnaruzhit tochku montirovaniya,
  2) sozdat/podgotovit /ESTER (prepare_ester_folder),
  3) (optsionalno) razvernut reliz/damp (scripts.usb_deploy_release),
  4) zapisat telemetriyu (latency p50/p95) i sostoyanie "seen" s TTL,
  5) (optsionalno) otpravit uvedomlenie, no NE zadavat voprosov.

Mosty:
- Yavnyy (Kibernetika ↔ Operatsii): edinyy refleks + izmerenie vremeni reaktsii (control through observation).
- Skrytyy 1 (Infoteoriya ↔ Diagnostika): minimum bitov (p50/p95 + ok/fail) → maksimum signala po kachestvu.
- Skrytyy 2 (Anatomiya ↔ Inzheneriya): kak proverka sukhozhilnogo refleksa — stimul → latentnost → otvet.

Zemnoy abzats:
Realnyy USB — eto fizika i pomekhi: odin i tot zhe stsenariy mozhet davat raznye zaderzhki iz‑za
pitaniya, USB‑khaba, progreva diska, planirovschika OS. Poetomu p50/p95 vazhnee «srednego»:
p50 — tipichno, p95 — «plokhoy den», kotoryy i ubivaet nadezhnost. Dzhitter nuzhen, chtoby
neskolko uzlov ne pytalis odnovremenno chitat/pisat odin i tot zhe nositel (anti‑stado).

# c=a+b
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import string
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# -------------------------
# Bezopasnye importy iz repozitoriya (esli est)
# -------------------------
try:
    from modules.selfmanage.usb_locator import list_usb_roots as _list_usb_roots  # type: ignore
    from modules.selfmanage.usb_locator import prepare_ester_folder as _prepare_ester_folder  # type: ignore
except Exception:  # noqa: BLE001
    _list_usb_roots = None  # type: ignore
    _prepare_ester_folder = None  # type: ignore

try:
    from utils.notify import try_notify as _try_notify  # type: ignore
except Exception:  # noqa: BLE001
    _try_notify = None  # type: ignore

try:
    from metrics.usb_agent_stats import USBStats as _USBStats  # type: ignore
except Exception:  # noqa: BLE001
    _USBStats = None  # type: ignore


# -------------------------
# Konfiguratsiya (env → default)
# -------------------------

def _default_state_dir() -> Path:
    # 1) yavnyy override
    if os.getenv("ESTER_STATE_DIR"):
        return Path(os.environ["ESTER_STATE_DIR"]).expanduser()

    # 2) XDG_STATE_HOME (Linux)
    xdg = os.getenv("XDG_STATE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "ester"

    # 3) OS-spetsifichno
    if platform.system().lower().startswith("win"):
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "Ester"
    return Path.home() / ".local" / "state" / "ester"


STATE_DIR = _default_state_dir()
STATE_FILE = STATE_DIR / "usb_zero_touch_state.json"
LOCK_FILE = STATE_DIR / "usb_zero_touch.lock"

# TTL dlya "seen" (sek). 0/<=0 = ne povtoryat nikogda.
SEEN_TTL_SEC_DEFAULT = int(os.getenv("ESTER_ZT_SEEN_TTL_SECONDS", str(24 * 3600)) or (24 * 3600))

# Period oprosa (sek), esli ne --once
POLL_INTERVAL_DEFAULT = int(os.getenv("ESTER_ZT_POLL_INTERVAL", "5") or 5)

# Anti-«stado» dzhitter (sek)
JITTER_DEFAULT = float(os.getenv("ESTER_ZT_JITTER_SECONDS", "0.2") or 0.2)

# Taymaut deploy (sek)
DEPLOY_TIMEOUT_SEC_DEFAULT = int(os.getenv("ESTER_ZT_DEPLOY_TIMEOUT_SECONDS", "180") or 180)

# Lock stale (sek): esli protsess umer, cherez eto vremya mozhno zakhvatit lock.
LOCK_STALE_SEC_DEFAULT = int(os.getenv("ESTER_ZT_LOCK_STALE_SECONDS", "600") or 600)

# Rezhim po umolchaniyu:
#  A: tolko prepare_ester_folder
#  B: prepare + deploy (esli zadan archive/dump)
AB_MODE_DEFAULT = (os.getenv("AB_MODE") or "b").strip().lower()


# Uvedomleniya: po umolchaniyu vklyucheny tolko esli est GUI (ne systemd/SSH bez DISPLAY)
def _default_headless() -> bool:
    if os.getenv("ESTER_ZT_HEADLESS") in ("1", "true", "yes"):
        return True
    if os.getenv("ESTER_ZT_HEADLESS") in ("0", "false", "no"):
        return False
    if platform.system().lower().startswith("win"):
        return False
    # Linux/mac: esli net displeya — skoree vsego headless
    return not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


HEADLESS_DEFAULT = _default_headless()


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


def _load_state() -> Dict[str, Any]:
    """
    Format:
      {
        "ver": 2,
        "seen": {
          "<mount>": {"first_ts": 123, "last_ts": 456, "count": 2}
        },
        "last": 123
      }
    """
    base: Dict[str, Any] = {"ver": 2, "seen": {}, "last": None}
    try:
        if STATE_FILE.exists():
            raw = STATE_FILE.read_text(encoding="utf-8", errors="replace")
            st = json.loads(raw) if raw.strip() else {}
            if not isinstance(st, dict):
                return base
            st.setdefault("ver", 2)
            st.setdefault("seen", {})
            st.setdefault("last", None)
            if not isinstance(st["seen"], dict):
                st["seen"] = {}
            return st
    except Exception:
        return base
    return base


def _save_state(st: Dict[str, Any]) -> None:
    try:
        payload = json.dumps(st, ensure_ascii=False, indent=2, sort_keys=True)
        _atomic_write_text(STATE_FILE, payload, encoding="utf-8")
    except Exception:
        pass


def _prune_seen(seen: Dict[str, Any], *, ttl_sec: int) -> Tuple[Dict[str, Any], int]:
    if ttl_sec <= 0:
        return seen, 0
    now = _now_ts()
    out: Dict[str, Any] = {}
    removed = 0
    for k, v in (seen or {}).items():
        try:
            last_ts = int((v or {}).get("last_ts") or (v or {}).get("ts") or 0)
        except Exception:
            last_ts = 0
        if last_ts and (now - last_ts) <= ttl_sec:
            out[k] = v
        else:
            removed += 1
    return out, removed


def _notify(title: str, body: str, *, headless: bool) -> None:
    if headless:
        return
    if _try_notify is None:
        return
    try:
        _try_notify(title, body)
    except Exception:
        return


# -------------------------
# Lok (O_EXCL lockfile) — krossplatformenno i bez storonnikh bibliotek
# -------------------------

def _acquire_lock(lock_file: Path, *, stale_sec: int) -> bool:
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    now = _now_ts()

    # Esli lock est i on staryy — probuem ubrat
    try:
        if lock_file.exists():
            age = now - int(lock_file.stat().st_mtime)
            if age > max(1, int(stale_sec)):
                try:
                    lock_file.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"pid": os.getpid(), "ts": now}, ensure_ascii=False))
        return True
    except FileExistsError:
        return False
    except Exception:
        # Esli ne mozhem zalochitsya — luchshe ne delat nichego.
        return False


def _release_lock(lock_file: Path) -> None:
    try:
        if lock_file.exists():
            lock_file.unlink()
    except Exception:
        pass


# -------------------------
# Fallback USB roots (esli usb_locator nedostupen)
# -------------------------

def _fallback_usb_roots() -> List[str]:
    roots: List[str] = []
    sysname = platform.system().lower()

    def add_if_mount(p: Path) -> None:
        try:
            if p.exists() and p.is_dir() and os.path.ismount(str(p)):
                roots.append(str(p.resolve()))
        except Exception:
            return

    if sysname.startswith("win"):
        # Windows: removable drives via GetDriveTypeW
        try:
            import ctypes  # noqa: WPS433

            GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW  # type: ignore[attr-defined]
            DRIVE_REMOVABLE = 2
            for letter in string.ascii_uppercase:
                drive = f"{letter}:/"
                try:
                    dtype = int(GetDriveTypeW(drive))
                except Exception:
                    continue
                if dtype == DRIVE_REMOVABLE:
                    roots.append(str(Path(drive).resolve()))
        except Exception:
            # krayne grubyy fallback: D..Z
            for letter in string.ascii_uppercase[3:]:
                p = Path(f"{letter}:/")
                if p.exists():
                    roots.append(str(p))
        return sorted(set(roots))

    # Linux/mac
    user = os.getenv("USER") or os.getenv("LOGNAME") or ""
    candidates: List[Path] = []
    if sysname.startswith("darwin"):
        candidates.append(Path("/Volumes"))
    else:
        # Linux
        if user:
            candidates += [Path("/run/media") / user, Path("/media") / user, Path("/media")]
        candidates += [Path("/mnt")]

    for base in candidates:
        try:
            if base.exists():
                for child in base.iterdir():
                    add_if_mount(child)
        except Exception:
            continue

    return sorted(set(roots))


def _list_mounts() -> List[str]:
    # primary: project usb_locator
    if _list_usb_roots is not None:
        try:
            roots = _list_usb_roots(require_sentinel=False) or []
            out: List[str] = []
            seen: Set[str] = set()
            for r in roots:
                try:
                    rp = str(Path(r).resolve())
                except Exception:
                    rp = str(r)
                if rp not in seen:
                    seen.add(rp)
                    out.append(rp)
            if out:
                return out
        except Exception:
            pass
    # fallback
    return _fallback_usb_roots()


def _prepare(mount: str) -> Tuple[bool, Optional[str], Optional[str]]:
    # returns (ok, root, error)
    if _prepare_ester_folder is None:
        return False, None, "prepare_ester_folder not available (missing modules.selfmanage.usb_locator)"
    try:
        root = _prepare_ester_folder(mount)
        return True, str(root), None
    except Exception as e:  # noqa: BLE001
        return False, None, f"{e.__class__.__name__}: {e}"


def _deploy(mount: str, archive: Optional[str], dump: Optional[str], *, timeout_sec: int) -> Dict[str, Any]:
    args = [sys.executable, "-m", "scripts.usb_deploy_release", "--mount", mount]
    if archive:
        args += ["--archive", archive]
    if dump:
        args += ["--dump", dump]

    try:
        cp = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, int(timeout_sec)),
            check=False,
        )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}", "args": args}

    payload: Dict[str, Any] = {}
    try:
        payload = json.loads((cp.stdout or "").strip() or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    ok = (cp.returncode == 0) or bool(payload.get("ok"))
    return {
        "ok": ok,
        "returncode": cp.returncode,
        "payload": payload,
        "stderr": (cp.stderr or "").strip(),
        "args": args,
    }


# -------------------------
# Mini-statistika (esli metrics.usb_agent_stats net)
# -------------------------

@dataclass
class _FallbackStats:
    lat: List[float] = field(default_factory=list)
    ok: int = 0
    fail: int = 0

    def record(self, latency_s: float, ok: bool) -> None:
        try:
            self.lat.append(float(latency_s))
        except Exception:
            pass
        if ok:
            self.ok += 1
        else:
            self.fail += 1

    @staticmethod
    def _pct(vals: List[float], p: float) -> Optional[float]:
        if not vals:
            return None
        v = sorted(vals)
        if len(v) == 1:
            return v[0]
        # nearest-rank-ish on index space
        k = max(0, min(len(v) - 1, int(round((p / 100.0) * (len(v) - 1)))))
        return v[k]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "count": len(self.lat),
            "ok": self.ok,
            "fail": self.fail,
            "p50_s": self._pct(self.lat, 50.0),
            "p95_s": self._pct(self.lat, 95.0),
        }


def _make_stats():
    if _USBStats is not None:
        try:
            return _USBStats()
        except Exception:
            return _FallbackStats()
    return _FallbackStats()


def _stats_record(stats, latency_s: float, ok: bool) -> None:
    try:
        stats.record(latency_s=latency_s, ok=ok)  # type: ignore[attr-defined]
    except Exception:
        try:
            stats.record(latency_s, ok)  # type: ignore[misc]
        except Exception:
            pass


def _stats_snapshot(stats) -> Dict[str, Any]:
    try:
        return stats.snapshot()  # type: ignore[attr-defined]
    except Exception:
        return {}


# -------------------------
# Osnovnoy tsikl
# -------------------------

def _should_process_mount(st: Dict[str, Any], mount: str, *, ttl_sec: int) -> bool:
    seen = st.get("seen") or {}
    if not isinstance(seen, dict):
        return True
    rec = seen.get(mount)
    if not rec:
        return True
    if ttl_sec <= 0:
        return False
    try:
        last_ts = int((rec or {}).get("last_ts") or (rec or {}).get("ts") or 0)
    except Exception:
        last_ts = 0
    if not last_ts:
        return True
    return (_now_ts() - last_ts) > ttl_sec


def run_once(
    archive: Optional[str],
    dump: Optional[str],
    *,
    ab_mode: str = AB_MODE_DEFAULT,
    headless: bool = HEADLESS_DEFAULT,
    jitter_sec: float = JITTER_DEFAULT,
    seen_ttl_sec: int = SEEN_TTL_SEC_DEFAULT,
    deploy_timeout_sec: int = DEPLOY_TIMEOUT_SEC_DEFAULT,
    lock_stale_sec: int = LOCK_STALE_SEC_DEFAULT,
) -> Dict[str, Any]:
    """
    Odin prokhod:
      - lock (chtoby 2 ekzemplyara ne gonyali USB parallelno),
      - enumerate mounts,
      - dlya novykh/prosrochennykh: prepare (+ deploy v B),
      - update state, return JSON.
    """
    # stdout v UTF-8 (osobenno vazhno na Windows)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    if not _acquire_lock(LOCK_FILE, stale_sec=int(lock_stale_sec)):
        return {"ok": True, "skipped": True, "reason": "lock-busy", "lock": str(LOCK_FILE)}

    try:
        st = _load_state()
        st["seen"], pruned = _prune_seen(st.get("seen") or {}, ttl_sec=int(seen_ttl_sec))

        mounts = _list_mounts()
        actions: List[Dict[str, Any]] = []
        stats = _make_stats()

        for m in mounts:
            if not _should_process_mount(st, m, ttl_sec=int(seen_ttl_sec)):
                continue

            # fiksiruem obnaruzhenie srazu (chtoby ne zatsiklitsya)
            now = _now_ts()
            rec = (st.get("seen") or {}).get(m) or {}
            if not isinstance(rec, dict):
                rec = {}
            rec.setdefault("first_ts", now)
            rec["last_ts"] = now
            rec["count"] = int(rec.get("count") or 0) + 1
            st.setdefault("seen", {})
            st["seen"][m] = rec

            t0 = time.perf_counter()

            if jitter_sec and jitter_sec > 0:
                time.sleep(random.uniform(0.0, float(jitter_sec)))

            ok_prepare, root, err = _prepare(m)

            t1 = time.perf_counter()
            latency = max(0.0, t1 - t0)

            rep: Dict[str, Any] = {
                "mount": m,
                "prepared": bool(ok_prepare),
                "root": root,
                "error": err,
                "latency_s": latency,
            }

            # Deploy tolko v B i tolko esli est vkhodnye artefakty
            mode = (ab_mode or "b").strip().lower()
            if mode == "b" and (archive or dump) and ok_prepare:
                rep["deploy"] = _deploy(m, archive=archive, dump=dump, timeout_sec=int(deploy_timeout_sec))

            actions.append(rep)
            _stats_record(stats, latency_s=latency, ok=bool(ok_prepare))

            # Notifikatsiya (informirovanie, bez voprosov)
            if ok_prepare:
                _notify("Ester: USB obrabotan", f"{m}\nroot={root}\nlatency={latency:.3f}s", headless=headless)
            else:
                _notify("Ester: USB oshibka", f"{m}\n{err}", headless=headless)

        st["last"] = _now_ts()
        _save_state(st)

        return {
            "ok": True,
            "actions": actions,
            "metrics": _stats_snapshot(stats),
            "state_file": str(STATE_FILE),
            "lock_file": str(LOCK_FILE),
            "pruned_seen": pruned,
            "config": {
                "headless": bool(headless),
                "jitter_sec": float(jitter_sec),
                "seen_ttl_sec": int(seen_ttl_sec),
                "deploy_timeout_sec": int(deploy_timeout_sec),
                "lock_stale_sec": int(lock_stale_sec),
                "ab_mode": (ab_mode or "b").strip().lower(),
            },
        }
    finally:
        _release_lock(LOCK_FILE)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB Zero-Touch Agent (portable)")

    ap.add_argument("--archive", type=str, default=os.getenv("ESTER_USB_DEPLOY_ARCHIVE", "").strip() or None)
    ap.add_argument("--dump", type=str, default=os.getenv("ESTER_USB_DEPLOY_DUMP", "").strip() or None)

    ap.add_argument("--interval", type=int, default=POLL_INTERVAL_DEFAULT)
    ap.add_argument("--once", action="store_true")

    ap.add_argument("--headless", action="store_true", default=HEADLESS_DEFAULT)
    ap.add_argument("--jitter", type=float, default=JITTER_DEFAULT)
    ap.add_argument("--seen-ttl", type=int, default=SEEN_TTL_SEC_DEFAULT)
    ap.add_argument("--deploy-timeout", type=int, default=DEPLOY_TIMEOUT_SEC_DEFAULT)
    ap.add_argument("--lock-stale", type=int, default=LOCK_STALE_SEC_DEFAULT)

    ap.add_argument("--ab", type=str, default=AB_MODE_DEFAULT, choices=["a", "b"])

    args = ap.parse_args(argv or [])

    # Odin raz
    result = run_once(
        args.archive,
        args.dump,
        ab_mode=args.ab,
        headless=bool(args.headless),
        jitter_sec=float(args.jitter),
        seen_ttl_sec=int(args.seen_ttl),
        deploy_timeout_sec=int(args.deploy_timeout),
        lock_stale_sec=int(args.lock_stale),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.once:
        return 0

    # Pulling
    try:
        while True:
            time.sleep(max(1, int(args.interval)))
            result = run_once(
                args.archive,
                args.dump,
                ab_mode=args.ab,
                headless=bool(args.headless),
                jitter_sec=float(args.jitter),
                seen_ttl_sec=int(args.seen_ttl),
                deploy_timeout_sec=int(args.deploy_timeout),
                lock_stale_sec=int(args.lock_stale),
            )
            # pechataem tolko esli est deystviya ili byli propuski/oshibki — menshe shuma
            if result.get("actions") or result.get("skipped") or not result.get("ok", True):
                print(json.dumps(result, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())