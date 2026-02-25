# -*- coding: utf-8 -*-
"""modules/thinking/rpa_workflows.py - JSON-workflow nad makrosami RPA (mysli → tsepochki deystviy).

Schema workflow (primer):
{
  "name": "hello",
  "steps": [
    {"macro": "open_portal_and_type", "args": {"text": "Hello from Ester"}, "retries": 1, "wait_ms": 200},
    {"macro": "click_text", "args": {"needle": "File"}, "on_fail": "continue"}
  ]
}

Podderzhka:
- retries (int, >=0), wait_ms (int, >=0), on_fail: "stop"|"continue" (by default "stop").
- Khranilische: data/workflows/<name>.json
- Planning: data/workflows/schedules.json:
  { "items": [ {"name":"hello","interval_sec":600,"enabled":true,"last_ts":0} ] }

MOSTY:
- Yavnyy: (Planirovanie ↔ Implementation) JSON-plany vyzyvayut makrosy RPA.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) fiksirovannyy alfavit shagov snizhaet entropiyu oshibok.
- Skrytyy #2: (Kibernetika ↔ Audit) edinyy treys (trace) kazhdoy tsepochki — zamknutaya petlya kontrolya.

ZEMNOY ABZATs:
Fayly na diske, bez BD i oblakov; tick-skript chitaet raspisanie i triggerit tsepochki. Oshibka shaga -
libo ostanov (po umolchaniyu), libo “prodolzhit”. Local and transparent.

# c=a+b"""
from __future__ import annotations
import os, json, time, threading
from typing import Any, Dict, List, Tuple

from modules.thinking.rpa_macros import list_macros, run_macro, MacroError
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROJECT_ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
WF_DIR = os.path.join(PROJECT_ROOT, "data", "workflows")
SCHED_PATH = os.path.join(WF_DIR, "schedules.json")

def _ensure_dirs() -> None:
    os.makedirs(WF_DIR, exist_ok=True)

def workflow_path(name: str) -> str:
    _ensure_dirs()
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", "."))
    return os.path.join(WF_DIR, f"{safe}.json")

def list_workflows() -> List[str]:
    _ensure_dirs()
    out: List[str] = []
    for fn in os.listdir(WF_DIR):
        if fn.endswith(".json") and fn not in ("schedules.json",):
            out.append(os.path.splitext(fn)[0])
    return sorted(out)

def load_workflow(name: str) -> Dict[str, Any]:
    p = workflow_path(name)
    if not os.path.exists(p):
        raise FileNotFoundError("workflow_not_found")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_workflow(name: str, spec: Dict[str, Any]) -> None:
    if not isinstance(spec, dict) or "steps" not in spec:
        raise ValueError("bad_spec")
    # validatsiya
    for st in spec.get("steps", []):
        m = (st.get("macro") or "").strip()
        if m not in set(list_macros()):
            raise ValueError(f"unknown_macro:{m}")
        if "retries" in st and int(st["retries"]) < 0:
            raise ValueError("bad_retries")
        if "wait_ms" in st and int(st["wait_ms"]) < 0:
            raise ValueError("bad_wait_ms")
        if "on_fail" in st and st["on_fail"] not in ("stop", "continue"):
            raise ValueError("bad_on_fail")
    spec = dict(spec)
    spec["name"] = name
    with open(workflow_path(name), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

def run_workflow(name: str, args_overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    spec = load_workflow(name)
    steps: List[Dict[str, Any]] = spec.get("steps", [])
    trace: List[Dict[str, Any]] = []
    for idx, st in enumerate(steps, 1):
        macro = st.get("macro")
        m_args = dict(st.get("args") or {})
        if args_overrides:
            # on top - general overrides
            m_args.update(args_overrides)
        retries = int(st.get("retries", 0))
        wait_ms = int(st.get("wait_ms", 0))
        on_fail = st.get("on_fail", "stop")
        attempt = 0
        last_err: str | None = None
        while True:
            attempt += 1
            try:
                res = run_macro(macro, m_args)
                trace.append({"step": idx, "macro": macro, "args": m_args, "ok": True, "res": res})
                break
            except MacroError as e:
                last_err = str(e)
                if attempt > retries:
                    trace.append({"step": idx, "macro": macro, "args": m_args, "ok": False, "error": last_err})
                    if on_fail == "stop":
                        return {"ok": False, "name": name, "trace": trace}
                    else:
                        # continue
                        break
                else:
                    # wait between repeats (if specified)
                    if wait_ms > 0:
                        time.sleep(wait_ms / 1000.0)
                    continue
    return {"ok": True, "name": name, "trace": trace}

# ---- Raspisanie (tick) ----

def _read_sched() -> Dict[str, Any]:
    _ensure_dirs()
    if not os.path.exists(SCHED_PATH):
        return {"items": []}
    with open(SCHED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_sched(obj: Dict[str, Any]) -> None:
    _ensure_dirs()
    with open(SCHED_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def sched_list() -> List[Dict[str, Any]]:
    return _read_sched().get("items", [])

def sched_save(items: List[Dict[str, Any]]) -> None:
    # simple validation
    for it in items:
        if not it.get("name"): raise ValueError("name_required")
        if "interval_sec" in it and int(it["interval_sec"]) <= 0: raise ValueError("bad_interval")
        it.setdefault("enabled", True)
        it.setdefault("last_ts", 0)
    _write_sched({"items": items})

def sched_tick(now_ts: int | None = None) -> Dict[str, Any]:
    now = int(now_ts or time.time())
    sched = _read_sched()
    changed = False
    runs: List[Dict[str, Any]] = []
    for it in sched.get("items", []):
        if not it.get("enabled", True): continue
        name = it.get("name")
        interval = int(it.get("interval_sec", 0))
        last_ts = int(it.get("last_ts", 0))
        if interval <= 0: continue
        if now - last_ts >= interval:
            # the time has come
            res = run_workflow(name, {})
            runs.append({"name": name, "ok": bool(res.get("ok")), "result": res})
            it["last_ts"] = now
            changed = True
    if changed:
        _write_sched(sched)
    return {"ok": True, "runs": runs, "now": now}