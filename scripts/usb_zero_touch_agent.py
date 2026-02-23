# -*- coding: utf-8 -*-
"""
scripts/usb_zero_touch_agent.py — agent «nulevogo treniya» dlya fleshek.

(GORYaChIY FIKS) Sovmestimost s modules.selfmanage.usb_locator:
  • Dlya konkretnogo mount ispolzuem prepare_ester_folder(mount).
  • find_or_prepare_usb() — bez argumentov, ostavlen dlya avtopoiska, no zdes ne primenyaetsya.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): regulyator s petley nablyudeniya (poll) i bez ruchnykh klikov.
- Skrytyy 1 (Infoteoriya ↔ Protokoly): ispolzuem stabilnyy CLI-kontrakt, ne trogaya myshlenie/pamyat Ester.
- Skrytyy 2 (Logika ↔ Bezopasnost): A/B-sloty — rezhim A «tolko podgotovka», rezhim B «avtodeploy».

Zemnoy abzats:
Polzovatel vstavlyaet fleshku — agent gotovit /ESTER i, esli nuzhno, pishet reliz/damp. Vse idempotentno.

# c=a+b
"""
from __future__ import annotations

import json
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from modules.selfmanage.usb_locator import list_usb_roots, prepare_ester_folder  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE_FILE = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))) / "usb_zero_touch_state.json"
DEFAULT_INTERVAL = int(os.getenv("ESTER_ZT_POLL_INTERVAL", "5"))  # sek

def _load_state() -> Dict[str, Any]:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"seen_mounts": {}, "last_ok": None, "last_err": None}

def _save_state(st: Dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _deploy_to_usb(mount: str, archive: Optional[str], dump: Optional[str], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"ok": True, "dry_run": True, "mount": mount, "action": ("archive" if archive else "dump")}
    if not archive and not dump:
        return {"ok": True, "skipped": True, "reason": "no-archive-or-dump"}
    args = [sys.executable, "-m", "scripts.usb_deploy_release", "--mount", mount]
    if archive:
        args += ["--archive", archive]
    if dump:
        args += ["--dump", dump]
    cp = subprocess.run(args, capture_output=True, text=True, check=False)
    payload = {}
    try:
        payload = json.loads(cp.stdout)
    except Exception:
        pass
    ok = (cp.returncode == 0) or bool(payload.get("ok"))
    return {"ok": ok, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr, "payload": payload}

def _unique_mounts() -> List[str]:
    roots = list_usb_roots() or []
    out: List[str] = []
    seen: Set[str] = set()
    for r in roots:
        p = str(Path(str(r)).resolve())
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

def run_once(archive: Optional[str], dump: Optional[str], dry_run: bool, ab_mode: str = "a") -> Dict[str, Any]:
    st = _load_state()
    mounts = _unique_mounts()
    prepared: List[Dict[str, Any]] = []
    deployed: List[Dict[str, Any]] = []

    for m in mounts:
        try:
            root = prepare_ester_folder(m)  # <-- fiks: podgotovka /ESTER na KONKRETNOM mount
            prepared.append({"mount": m, "ester_root": root, "ok": True})
        except Exception as e:
            prepared.append({"mount": m, "ok": False, "error": f"{e.__class__.__name__}: {e}"})
            continue

        if (ab_mode or "a").lower() == "b":
            rep = _deploy_to_usb(m, archive=archive, dump=dump, dry_run=dry_run)
            deployed.append({"mount": m, **rep})

        st["seen_mounts"][m] = int(time.time())

    st["last_ok"] = int(time.time())
    _save_state(st)
    return {"ok": True, "mounts": mounts, "prepared": prepared, "deployed": deployed, "state_file": str(STATE_FILE)}

def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Ester USB Zero-Touch Agent")
    ap.add_argument("--archive", type=str, default=os.getenv("ESTER_USB_DEPLOY_ARCHIVE", "").strip() or None)
    ap.add_argument("--dump", type=str, default=os.getenv("ESTER_USB_DEPLOY_DUMP", "").strip() or None)
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv or [])
    ab_mode = (os.getenv("AB_MODE") or "A").strip().lower()

    if args.once:
        print(json.dumps(run_once(archive=args.archive, dump=args.dump, dry_run=args.dry_run, ab_mode=ab_mode), ensure_ascii=False, indent=2))
        return 0
    try:
        while True:
            print(json.dumps(run_once(archive=args.archive, dump=args.dump, dry_run=args.dry_run, ab_mode=ab_mode), ensure_ascii=False, indent=2))
            time.sleep(max(1, int(args.interval)))
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
