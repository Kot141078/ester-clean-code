# -*- coding: utf-8 -*-
from __future__ import annotations

"""listeners/usb_recovery_autorun.py — USB autorun + recovery listener.

Tekuschaya oshibka:
  expected an indented block after 'if' statement
Prichina: v kontse fayla bylo `if __name__ == "__main__":` bez tela.

Chto sdelano:
- Ispravlen sintaksis (korrektnyy __main__).
- Privedeny k UTF-8 chitaemye dokstringi/kommentarii (vmesto krakozyabr).
- Ukreplena idempotentnost autorun: garantiruem strukturu zhurnala i zapis po plan.id.
- Dobavlen Windows-friendly fallback poiska USB (esli modules.usb.recovery nedostupen):
  skan diskov C:..Z: i vybor tekh, gde est papka ESTER.
- Dobavleny myagkie predokhraniteli po razmeru:
  USB_MAX_PLAN_MB (po umolchaniyu 64), USB_COPY_MAX_MB (po umolchaniyu 2048).
- AB_MODE: A = dry-run (logiruem, ne ispolnyaem), B = primenyaem.

Mosty (trebovanie):
- Yavnyy most: USB → plan.json → executor/run_job → izmenenie sostoyaniya uzla (realnoe deystvie pod L4).
- Skrytye mosty:
  1) Infoteoriya ↔ praktika: idempotency po plan.id — “szhatie” istorii vypolneniya v odin fakt «uzhe sdelano».
  2) Kibernetika ↔ ekspluatatsiya: AB=A kak circuit breaker — kontur nablyudaet, no ne deystvuet.

ZEMNOY ABZATs: vnizu fayla.
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Obschie peremennye ---
AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
AUTORUN_LOG_FILE = STATE_DIR / "autorun_log.json"

# --- I/O helpers ---
def _read_json(p: Path, dflt: Any) -> Any:
    """Bezopasnoe chtenie JSON fayla."""
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dflt


def _write_json_atomic(p: Path, obj: dict) -> None:
    """Atomarnaya zapis JSON (cherez .tmp + replace)."""
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


# --- USB discovery ---
def _get_usb_targets() -> List[Dict[str, Any]]:
    """Poluchenie spiska podklyuchennykh USB tseley.

    Pytaemsya ispolzovat kanonicheskiy modul, inache — fallback.
    Vozvraschaem spisok dict s klyuchom 'mount' (stroka).
    """
    try:
        from modules.usb.recovery import list_usb_targets  # type: ignore

        targets = list_usb_targets() or []
        out = []
        for t in targets:
            m = (t or {}).get("mount")
            if m:
                out.append({"mount": str(m)})
        return out
    except Exception:
        # Fallback: Linux mountpoints
        mounts: List[Dict[str, Any]] = []
        for r in (Path("/media"), Path("/mnt")):
            if r.exists():
                for p in r.iterdir():
                    if p.is_dir():
                        mounts.append({"mount": str(p)})
        # Fallback: Windows — ischem diski s papkoy ESTER
        if os.name == "nt":
            for code in range(ord("C"), ord("Z") + 1):
                root = Path(chr(code) + ":\\")
                ester_dir = root / "ESTER"
                if ester_dir.exists() and ester_dir.is_dir():
                    mounts.append({"mount": str(root)})
        # Uberem dubli
        seen = set()
        uniq: List[Dict[str, Any]] = []
        for t in mounts:
            m = t.get("mount")
            if not m:
                continue
            if m in seen:
                continue
            seen.add(m)
            uniq.append({"mount": m})
        return uniq


# --- Autorun Plan logic ---
def _subst(s: str, USB: Path, HOME: Path) -> str:
    """Zamenyaet pleyskholdery $USB i $HOME."""
    return str(s).replace("$USB", str(USB)).replace("$HOME", str(HOME))


def _exec_plan(usb_root: Path, plan: Dict[str, Any], dry: bool) -> Dict[str, Any]:
    """Vypolnyaet shagi iz autorun plana."""
    steps = plan.get("steps", []) or []
    HOME = Path.home()
    done: List[Dict[str, Any]] = []

    for st in steps:
        if not isinstance(st, dict):
            done.append({"skip": "non-dict-step"})
            continue

        act = st.get("action")
        if act == "copy_dir":
            src = Path(_subst(st.get("from", ""), usb_root, HOME)).resolve()
            dst = Path(_subst(st.get("to", ""), usb_root, HOME)).resolve()

            if dry:
                done.append({"copy_dir": {"from": str(src), "to": str(dst), "dry": True}})
                continue

            if not src.exists() or not src.is_dir():
                raise RuntimeError(f"copy-src-missing: {src}")

            if dst.exists():
                shutil.rmtree(dst)

            max_mb = int(os.getenv("USB_COPY_MAX_MB", "2048"))
            files_to_copy = [p for p in src.rglob("*") if p.is_file()]
            total_size = 0
            for p in files_to_copy:
                try:
                    total_size += int(p.stat().st_size)
                except Exception:
                    pass

            if total_size > max_mb * 1024 * 1024:
                raise RuntimeError(f"copy-too-large: size {total_size} exceeds limit {max_mb} MB")

            dst.parent.mkdir(parents=True, exist_ok=True)
            for p in files_to_copy:
                rel_path = p.relative_to(src)
                target_path = dst / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target_path)

            done.append({"copy_dir": {"from": str(src), "to": str(dst), "bytes": total_size}})

        elif act == "proj_build_publish":
            args = st.get("args") or {}
            if dry:
                done.append({"proj_build_publish": {"dry": True, "args": args}})
                continue
            from modules.jobs.executor import run_job  # type: ignore

            job = {"type": "proj_build_publish", "args": args}
            res = run_job(job)
            done.append({"proj_build_publish": res})

        else:
            done.append({"skip": act})

    return {"ok": True, "steps": done}


def handle_autorun_plan(mount_point: str, seen_plans: dict) -> None:
    """Proveryaet i vypolnyaet autorun plan na ustroystve (idempotent po plan.id)."""
    # podderzhivaem dva rezhima: plan lezhit na korne USB ili vnutri ESTER
    mp = Path(mount_point)

    # Esli mount_point — koren diska, ischem ESTER vnutri; inache predpolagaem, chto mount_point uzhe ESTER-root
    usb_ester_dir = mp / "ESTER" if (mp / "ESTER").exists() else mp
    plan_path = usb_ester_dir / "autorun" / "plan.json"

    if not plan_path.exists():
        return

    max_plan_mb = int(os.getenv("USB_MAX_PLAN_MB", "64"))
    try:
        if plan_path.stat().st_size > max_plan_mb * 1024 * 1024:
            print(f"[autorun-skip] plan too large: {plan_path}", flush=True)
            return
    except Exception:
        pass

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[autorun-fail] parse plan {plan_path}: {e}", flush=True)
        return

    if not isinstance(plan, dict):
        return

    # normalizuem zhurnal
    if not isinstance(seen_plans.get("done"), dict):
        seen_plans["done"] = {}

    plan_id = str(plan.get("id") or "").strip()
    if not plan_id:
        return

    if plan_id in seen_plans["done"]:  # idempotent
        return

    try:
        res = _exec_plan(usb_ester_dir, plan, dry=(AB != "B"))
        seen_plans["done"][plan_id] = int(time.time())
        _write_json_atomic(AUTORUN_LOG_FILE, seen_plans)

        print(
            json.dumps(
                {
                    "ts": int(time.time()),
                    "type": "autorun",
                    "usb": str(usb_ester_dir),
                    "plan": plan_id,
                    "ab": AB,
                    "res_ok": bool(res.get("ok", False)),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    except Exception as e:
        print(f"[autorun-exec-fail] plan_id={plan_id}, error: {e}", flush=True)


# --- Recovery logic ---
def handle_recovery(mount_point: str, recovery_cfg: dict) -> bool:
    """Proveryaet marker i zapuskaet vosstanovlenie (esli vklyucheno)."""
    try:
        from modules.usb.recovery import scan_usb, apply_recover  # type: ignore
    except Exception as e:
        print(f"[recovery-fail] missing modules.usb.recovery: {e}", flush=True)
        return False

    rep = scan_usb(mount_point)
    if rep.get("ok") and (rep.get("auto_mark") or not recovery_cfg.get("require_mark", True)):
        if AB == "B":
            res = apply_recover(mount_point, recovery_cfg)
            status = "[recovery-ok]" if res.get("ok") else "[recovery-fail]"
            print(status, str(res)[:300], flush=True)
        else:
            print("[recovery-dry]", mount_point, flush=True)
        return True
    return False


# --- Main loop ---
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ester USB autorun and recovery listener")
    ap.add_argument("--loop", action="store_true", help="Run in a continuous loop")
    ap.add_argument("--interval", type=int, default=5, help="Polling interval (sec)")
    args = ap.parse_args(argv)

    is_recovery_enabled = bool(int(os.getenv("USB_RECOVERY_ENABLE", "0")))
    recovery_cfg: dict = {}
    if is_recovery_enabled:
        try:
            from modules.usb.recovery_settings import load_usb_recovery_settings  # type: ignore

            recovery_cfg = load_usb_recovery_settings() or {}
            print("[usb-recovery] enabled", flush=True)
        except Exception as e:
            print(f"[usb-recovery] enabled but settings load failed: {e}", flush=True)
            recovery_cfg = {}
    else:
        print("[usb-recovery] disabled", flush=True)

    seen_plans = _read_json(AUTORUN_LOG_FILE, {"done": {}})
    if not isinstance(seen_plans, dict):
        seen_plans = {"done": {}}
    if not isinstance(seen_plans.get("done"), dict):
        seen_plans["done"] = {}

    seen_mounts_recovery = set()

    try:
        while True:
            targets = _get_usb_targets()
            for t in targets:
                mount_point = (t or {}).get("mount")
                if not mount_point:
                    continue

                if is_recovery_enabled and mount_point not in seen_mounts_recovery:
                    if handle_recovery(mount_point, recovery_cfg):
                        seen_mounts_recovery.add(mount_point)

                handle_autorun_plan(mount_point, seen_plans)

            if not args.loop:
                break
            time.sleep(max(2, int(args.interval)))
    except KeyboardInterrupt:
        return 0
    except ImportError as e:
        print(f"Error: Missing required modules. Details: {e}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Eto “dezhurnyy avtomat” u dverey: uvidel nositel s planom — sdelal po instruktsii.
No khoroshiy avtomat obyazan imet predokhranitel. Zdes predokhraniteli — AB_MODE (A=sukho),
limity razmerov (plan/kopirovanie) i idempotentnost po plan.id: odin plan = odin raz.
"""