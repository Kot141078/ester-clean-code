# -*- coding: utf-8 -*-
"""
modules/thinking/selfdrive.py — edinyy avtonomnyy tsikl:
  goal → Think/Plan → Safety(assess/simulate/decide) → Act(cascade/pipeline) → Reflect → (optional retry) → log.

Naznachenie:
- Prevratit mysli Ester v deystviya s obyazatelnym safety-barerom.
- Podderzhat «dlinnye tseli» (missii) s ponyatnymi ostanovkami i perezapuskami.
- Davat obyasnimyy zhurnal: pochemu poshli/ne poshli, i chto budet dalshe.

MOSTY:
- Yavnyy: (Mysl ↔ Deystvie) — safety mezhdu planom i aktom.
- Skrytyy #1: (Infoteoriya ↔ Byudzhet) — stoimost/risk ogranichivayut aktivnost.
- Skrytyy #2: (Kibernetika ↔ Ustoychivost) — avtopovtory pri «near», ostanov pri riske.

ZEMNOY ABZATs:
Inzhenerno — dispetcher shaga/pauzy/povtora s zhurnalom i byudzhetami. Prakticheski — «avtopilot deystviy»: dumaem, otsenivaem, delaem, podvodim itog, povtoryaem esli est smysl.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os, time, threading

from modules.memory import store
from modules.memory.events import record_event
from modules.thinking import cascade as CAS
from modules.thinking import pipelines as TP
from modules.thinking import action_safety as AS
from modules.thinking import missions as MS  # optsionalno: esli aktivny missii
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_STATE = {
    "enabled": False,
    "running": False,
    "last_run_ts": 0,
    "last_result": None,
    "log": []  # koltsevoy bufer poslednikh 100 zapisey
}
_LOCK = threading.Lock()
_THREAD: Optional[threading.Thread] = None
_STOP = False

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store as _store  # type: ignore
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

def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)

def _max_steps() -> int:
    try: return max(1, int(_env("ESTER_SELDDRIVE_MAX_STEPS", "6")))
    except: return 6

def _retry_limit() -> int:
    try: return max(0, int(_env("ESTER_SELDDRIVE_RETRY_LIMIT", "2")))
    except: return 2

def _wait_sec() -> int:
    try: return max(1, int(_env("ESTER_SELDDRIVE_WAIT_SEC", "5")))
    except: return 5

def _enabled_env() -> bool:
    return _env("ESTER_SELDDRIVE_ENABLED", "0") == "1"

def _log(entry: Dict[str, Any]) -> None:
    with _LOCK:
        _STATE["log"].append(entry)
        if len(_STATE["log"]) > 100:
            _STATE["log"] = _STATE["log"][-100:]

def _decide_safety(action: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    return AS.decide(action, meta)

def _simulate(action: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    try: return AS.simulate(action, meta, trials=40)
    except Exception: return {"ok": False, "action": action, "trials": 0}

def _reflect(result: Dict[str, Any]) -> None:
    txt = result.get("summary") or "SelfDrive: zaversheno."
    memory_add("summary", f"[selfdrive] {txt}", {"result": result})
    record_event("selfdrive", "reflect", True, {"msg": txt})

def _plan(goal: str, params: Dict[str, Any]) -> Dict[str, Any]:
    # minimalnyy plan — cherez pipelines decision_plan + analyze_text
    spec = TP.make_spec("decision_plan", goal, {"objective": goal, "options": [goal, "issledovat", "otlozhit"]})
    out1 = TP.run_pipeline(spec)
    # Vtoroy shag — analiz formulirovki tseli
    out2 = TP.run_pipeline(TP.make_spec("analyze_text", goal, {"text": goal}))
    return {
        "ok": bool(out1.get("ok", True)),
        "plan": {"choice": out1.get("result", {}).get("choice"), "scores": out1.get("result", {}).get("scores", []),
                 "terms": out2.get("result", {}).get("terms", [])}
    }

def _act(goal: str, params: Dict[str, Any]) -> Dict[str, Any]:
    # deystvie delaem kaskadom (on vnutri vyzyvaet pipelines)
    return CAS.run_cascade(goal, {"params": params})

def run_once(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Edinichnyy progon petli: Think/Plan → Safety → Act → Reflect (+avtopovtory pri near).
    """
    params = params or {}
    t0 = int(time.time())
    steps = []
    record_event("selfdrive", "start", True, {"goal": goal})
    try:
        _mirror_background_event(
            f"[SELFDRIVE_START] goal={goal}",
            "selfdrive",
            "start",
        )
    except Exception:
        pass

    # 1) Think/Plan
    steps.append({"stage": "think", "msg": f"osmyslyayu tsel: {goal}"})
    p = _plan(goal, params)
    steps.append({"stage": "plan", "plan": p})

    # 2) Safety (otsenka + simulyatsiya + reshenie)
    # Budem otsenivat abstraktnoe deystvie «execute_goal» s metadannymi po planu
    meta = {
        "steps": 2,
        "requires_admin": bool(params.get("requires_admin")),
        "irreversible": bool(params.get("irreversible")),
        "network": bool(params.get("network")),
        "unknown_vendor": bool(params.get("unknown_vendor")),
        "scale": float(params.get("scale", 1.0))
    }
    sim = _simulate("execute_goal", meta)
    steps.append({"stage": "safety_sim", "sim": sim})

    dec = _decide_safety("execute_goal", meta)
    steps.append({"stage": "safety_decide", "decision": dec})

    if dec.get("decision") == "deny":
        result = {"ok": False, "summary": "SelfDrive ostanovlen: risk/byudzhet ne pozvolyaet.", "steps": steps}
        _reflect(result)
        _STATE.update({"last_run_ts": int(time.time()), "last_result": result})
        _log({"ts": int(time.time()), "goal": goal, "result": "deny"})
        try:
            _mirror_background_event(
                f"[SELFDRIVE_DENY] goal={goal}",
                "selfdrive",
                "deny",
            )
        except Exception:
            pass
        return result

    if dec.get("decision") == "needs_user_consent":
        # fiksiruem zapros soglasiya v pamyati — UI mozhet podkhvatit
        memory_add("event", f"selfdrive: trebuetsya soglasie na deystvie '{goal}'", {"decision": dec})
        result = {"ok": False, "summary": "Nuzhno soglasie polzovatelya.", "steps": steps}
        _reflect(result)
        _STATE.update({"last_run_ts": int(time.time()), "last_result": result})
        _log({"ts": int(time.time()), "goal": goal, "result": "consent"})
        try:
            _mirror_background_event(
                f"[SELFDRIVE_CONSENT] goal={goal}",
                "selfdrive",
                "consent",
            )
        except Exception:
            pass
        return result

    # 3) Act (+avtopovtor pri near)
    retries = 0
    act_out = _act(goal, params)
    steps.append({"stage": "act", "out": {"summary": act_out.get("summary"), "ok": act_out.get("ok", True)}})

    # prostaya evristika near-popytki: esli safety p_success < 0.6 i rezultat ok, ne trogaem;
    # esli p_success v diapazone [0.35..0.6) i rezultat «ok», zavershaem; esli act ok==False i est «near» v simulyatsii — povtoryaem do RETRY_LIMIT
    p_succ = float(sim.get("p_success", 0.0))
    hist = sim.get("hist", {})
    while (not act_out.get("ok", True)) and (hist.get("near", 0) > hist.get("success", 0)) and (retries < _retry_limit()):
        retries += 1
        time.sleep(_wait_sec())
        act_out = _act(goal + f" [retry:{retries}]", params)
        steps.append({"stage": "act_retry", "retry": retries, "ok": act_out.get("ok", True)})

    # 4) Reflect
    final_summary = act_out.get("summary") or ("SelfDrive zavershen." if act_out.get("ok", True) else "SelfDrive zavershen s oshibkoy.")
    result = {"ok": act_out.get("ok", True), "summary": final_summary, "steps": steps, "retries": retries}
    _reflect(result)

    t1 = int(time.time())
    _STATE.update({"last_run_ts": t1, "last_result": result})
    _log({"ts": t1, "goal": goal, "result": "ok" if result["ok"] else "fail", "retries": retries})
    try:
        _mirror_background_event(
            f"[SELFDRIVE_DONE] goal={goal} ok={int(result['ok'])} retries={retries}",
            "selfdrive",
            "done",
        )
    except Exception:
        pass
    return result

def _loop():
    while not _STOP:
        if not _enabled_env():
            time.sleep(1); continue
        try:
            # esli est missii i oni vklyucheny — podkhvatyvaem blizhayshuyu k tikanyu
            if MS.status().get("enabled"):
                # missii sami tikayut; zdes — «podstrakhovka»: vozmem blizhayshuyu queued dlya samoprogona
                lst = MS.list_().get("items", [])
                queued = [m for m in lst if m.get("status") in ("queued",) and m.get("next_ts", 0) <= int(time.time())]
                if queued:
                    goal = queued[0]["goal"]
                    run_once(goal, queued[0].get("params") or {})
            time.sleep(_wait_sec())
        except Exception:
            try:
                _mirror_background_event(
                    "[SELFDRIVE_LOOP_ERROR]",
                    "selfdrive",
                    "loop_error",
                )
            except Exception:
                pass
            time.sleep(2)

def enable() -> Dict[str, Any]:
    global _THREAD, _STOP
    if _STATE["running"]:
        _STATE["enabled"] = _enabled_env()
        return {"ok": True, **_STATE}
    if not _enabled_env():
        _STATE["enabled"] = False
        return {"ok": False, "error": "disabled_by_env", **_STATE}
    _STOP = False
    _THREAD = threading.Thread(target=_loop, name="ester-selfdrive", daemon=True)
    _THREAD.start()
    _STATE.update({"enabled": True, "running": True})
    try:
        _mirror_background_event(
            "[SELFDRIVE_START_LOOP]",
            "selfdrive",
            "loop_start",
        )
    except Exception:
        pass
    return {"ok": True, **_STATE}

def disable() -> Dict[str, Any]:
    global _STOP
    _STOP = True
    _STATE.update({"running": False})
    try:
        _mirror_background_event(
            "[SELFDRIVE_STOP]",
            "selfdrive",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, **_STATE}

def status() -> Dict[str, Any]:
    return {"ok": True, **_STATE}

def log() -> Dict[str, Any]:
    with _LOCK:
        return {"ok": True, "items": list(_STATE["log"])}