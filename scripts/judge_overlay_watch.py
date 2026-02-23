# -*- coding: utf-8 -*-
"""
scripts/judge_overlay_watch.py — storozh overlay-fayla Judge (polling, bez zavisimostey).

Povedenie:
  • Sledit za ESTER_JUDGE_SLOTS_PATH (ili --path).
  • Pri izmenenii soderzhimogo (mtime/hash) — validiruet JSON i vyzyvaet komandu perezagruzki Judge:
      - iz ENV ESTER_JUDGE_RELOAD_CMD ili argumenta --cmd.
      - esli ne zadano — delaet no-op i pishet preduprezhdenie v stdout.
  • Period oprosa — ESTER_JUDGE_WATCH_INTERVAL (ili --interval), po umolchaniyu 2 sek.

CLI:
  python -m scripts.judge_overlay_watch [--path FILE] [--cmd "..."] [--interval 2] [--once]

Mosty:
  • Yavnyy (Orkestratsiya ↔ Ekspluatatsiya): fayl → yavnaya komanda perezapuska, bez vmeshatelstva v Judge.
  • Skrytyy 1 (Infoteoriya ↔ Nadezhnost): sravnenie po kheshu/mtime — minimum lozhnykh srabatyvaniy.
  • Skrytyy 2 (Praktika ↔ Bezopasnost): no-op po umolchaniyu — nulevaya veroyatnost neozhidannoy perezagruzki.

Zemnoy abzats:
Eto "storozh u dveri": esli konfig podskazok izmenilsya, on vezhlivo postuchit v Judge tak,
kak ty skazhesh (systemctl, HTTP, skript) — sam Judge my ne trogaem.

# c=a+b
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw), raw
    except Exception:
        return None, None

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _reload(cmd: str | None) -> Dict[str, Any]:
    if not cmd:
        return {"ok": True, "skipped": True, "reason": "no-cmd"}
    try:
        cp = subprocess.run(cmd if isinstance(cmd, list) else shlex.split(cmd), capture_output=True, text=True, check=False)
        return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr, "cmd": cmd}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}", "cmd": cmd}

def run_once(path: Path, cmd: Optional[str]) -> Dict[str, Any]:
    rep: Dict[str, Any] = {"path": str(path)}
    if not path.exists():
        rep.update({"ok": True, "exists": False, "skipped": True})
        return rep
    data, raw = _read_json(path)
    if data is None or raw is None:
        return {"ok": False, "error": "invalid-json"}
    rep["exists"] = True
    rep["hash"] = _hash(raw)
    rep["valid"] = "slotA" in data and "slotB" in data
    if not rep["valid"]:
        return {"ok": False, "error": "invalid-schema", **rep}
    # Dlya --once prosto vozvraschaem slepok
    rep["ok"] = True
    return rep

def loop(path: Path, cmd: Optional[str], interval: float) -> int:
    last_hash = None
    while True:
        if not path.exists():
            time.sleep(interval)
            continue
        data, raw = _read_json(path)
        if data is None or raw is None:
            print(json.dumps({"ok": False, "error": "invalid-json"}), flush=True)
            time.sleep(interval)
            continue
        h = _hash(raw)
        if last_hash is None:
            last_hash = h
        elif h != last_hash:
            # Izmenenie: probuem perezagruzit Judge
            res = _reload(cmd)
            event = {"ts": int(time.time()), "changed": True, "hash": h, "prev": last_hash, "reload": res}
            print(json.dumps(event, ensure_ascii=False), flush=True)
            last_hash = h
        time.sleep(interval)

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ester Judge Overlay Watcher")
    ap.add_argument("--path", type=str, default=os.getenv("ESTER_JUDGE_SLOTS_PATH", str(Path.home() / ".ester" / "judge_slots.json")))
    ap.add_argument("--cmd", type=str, default=os.getenv("ESTER_JUDGE_RELOAD_CMD", "").strip() or None)
    ap.add_argument("--interval", type=float, default=float(os.getenv("ESTER_JUDGE_WATCH_INTERVAL", "2")))
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv or [])

    p = Path(os.path.expanduser(args.path))
    if args.once:
        print(json.dumps(run_once(p, args.cmd), ensure_ascii=False, indent=2))
        return 0
    try:
        return loop(p, args.cmd, args.interval) or 0
    except KeyboardInterrupt:
        return 0

if __name__ == "__main__":
    raise SystemExit(main())