# -*- coding: utf-8 -*-
"""modules/thinking/volition_pulse.py - “puls voli”: configuriruemyy nabor avtodeystviy.

Config(VOLITION_CFG, JSON):
{
  "budget": 0.25,
  "tasks": [
    {"kind":"health.check", "every_min":30},
    {"kind":"media.watch.tick", "every_min":60, "args":{"limit":5}},
    {"kind":"scheduler.tick", "every_min":1},
    {"kind":"snapshot.daily", "every_min":1440, "args":{"roots":["modules","routes","middleware","services"]}}
  ],
  "last": {}
}

Podderzhivaemye kind:
- health.check → /resilience/health/check
- media.watch.tick → action "media.watch.tick"
- scheduler.tick → action "scheduler.tick"
- snapshot.daily → actions "release.snapshot" (zavodit manifest/arkhiv)
- backup.rot → actions "backup.run" (esli nastroeny targets)

Mosty:
- Yavnyy: (Volya ↔ Planirovschik) prostye, bezopasnye regulyarnye deystviya.
- Skrytyy #1: (Ekonomika ↔ CostFence) uchityvaet obschiy byudzhet na tik.
- Skrytyy #2: (Nadezhnost ↔ Avtokatbek) zaprosy chteniya/legkie write bez izmeneniya kontraktov.

Zemnoy abzats:
Budilnik, kotoryy sama Ester sebe stavit: sometimes proverit zdorove, sometimes “podpylesosit” media, raz v den - sobrat chemodan.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("VOLITION_AB","A") or "A").upper()
CFG_PATH = os.getenv("VOLITION_CFG","data/volition/pulse.json")
MAX_STEPS = int(os.getenv("VOLITION_MAX_STEPS","6") or "6")
DEFAULT_BUDGET = float(os.getenv("VOLITION_DEFAULT_BUDGET","0.25") or "0.25")

def _ensure():
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    if not os.path.isfile(CFG_PATH):
        json.dump({
            "budget": DEFAULT_BUDGET,
            "tasks": [
                {"kind":"health.check","every_min":30},
                {"kind":"media.watch.tick","every_min":60,"args":{"limit":5}},
                {"kind":"scheduler.tick","every_min":1},
                {"kind":"snapshot.daily","every_min":1440,"args":{"roots":["modules","routes","middleware","services"]}}
            ],
            "last": {}
        }, open(CFG_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def load_config() -> Dict[str,Any]:
    _ensure()
    return json.load(open(CFG_PATH,"r",encoding="utf-8"))

def save_config(obj: Dict[str,Any]) -> Dict[str,Any]:
    _ensure()
    cur=load_config(); cur.update(obj or {})
    json.dump(cur, open(CFG_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "config": cur}

def _cost_ok(need: float) -> bool:
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        rep=evaluate("volition", need)
        return bool(rep.get("allow",True))
    except Exception:
        return True

def _call_action(name: str, args: Dict[str,Any]) -> Dict[str,Any]:
    try:
        from modules.thinking.action_registry import invoke  # type: ignore
        return invoke(name, args or {})
    except Exception as e:
        return {"ok": False, "error": f"invoke:{e}"}

def _health() -> Dict[str,Any]:
    try:
        from modules.resilience.health import check  # type: ignore
        return check()
    except Exception as e:
        return {"ok": False, "error": f"health:{e}"}

def _snapshot(roots: List[str]) -> Dict[str,Any]:
    try:
        from modules.release.packager import snapshot  # type: ignore
        return snapshot(roots, "ester")
    except Exception as e:
        return {"ok": False, "error": f"snapshot:{e}"}

def tick(now: float | None = None) -> Dict[str,Any]:
    cfg=load_config()
    budget=float(cfg.get("budget", DEFAULT_BUDGET))
    last=cfg.get("last") or {}
    tasks=list(cfg.get("tasks") or [])
    now = now or time.time()
    ran=[]; skipped=[]
    steps=0
    for t in tasks:
        if steps>=MAX_STEPS: break
        kind=t.get("kind",""); every=int(t.get("every_min",60))
        last_ts=float(last.get(kind,0))
        if now - last_ts < every*60:
            skipped.append({"kind": kind, "why":"not_due"}); continue
        # budget estimate (rough): each step is considered ~0.05
        need=0.05
        if AB=="A" and not _cost_ok(need):
            skipped.append({"kind": kind, "why":"budget"}); continue
        # vypolnenie
        if kind=="health.check":
            rep=_health()
        elif kind=="media.watch.tick":
            rep=_call_action("media.watch.tick", t.get("args") or {})
        elif kind=="scheduler.tick":
            rep=_call_action("scheduler.tick", {})
        elif kind=="snapshot.daily":
            rep=_snapshot(list((t.get("args") or {}).get("roots") or ["modules","routes","middleware","services"]))
        elif kind=="backup.rot":
            rep=_call_action("backup.run", t.get("args") or {})
        else:
            rep={"ok": False, "error":"unknown_task"}
        ran.append({"kind": kind, "rep": rep})
        if rep.get("ok"):
            last[kind]=now
        steps+=1
    cfg["last"]=last
    save_config(cfg)
    return {"ok": all((x.get("rep") or {}).get("ok",True) for x in ran), "ran": ran, "skipped": skipped, "steps": steps, "budget": budget}
# c=a+b