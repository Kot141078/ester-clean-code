# -*- coding: utf-8 -*-
"""
modules/thinking/think_core.py — minimalnoe yadro «dumaniya» s sovmestimymi
interfeysami dlya chat_routes: start/stop/status + THINKER.

Mosty:
- Yavnyy: chat_routes (/thinking/*) ↔ etot modul (start/stop/status).
- Skrytyy #1: (Memory ↔ Sobytiya) — myagkiy vyzov record_thought (esli est).
- Skrytyy #2: (Planirovschik ↔ Ispolnenie) — myagkie zaglushki plan/execute dlya drop-in.

Zemnoy abzats:
Eto bezopasnye «knopki» upravleniya bez fonovykh potokov: zapusk, ostanovka i status
tsikla. Nikakikh vneshnikh zavisimostey; vse integratsii — myagkie, cherez try/except.
# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os, json, time
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

__all__ = ["think", "THINKER", "start", "stop", "status"]

# ---------------------------------------------------------------------------
# Myagkie integratsii
# ---------------------------------------------------------------------------

# record_thought (myagko)
try:
    from modules.memory.events import record_thought  # type: ignore
except Exception:
    def record_thought(goal: str, conclusion: str, success: bool) -> None:  # type: ignore
        base = os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")
        path = Path(base) / "logs" / "thoughts.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"goal": goal, "conclusion": conclusion, "success": success}, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

# integrate (myagko)
try:
    from modules.thinking.memory_bridge import integrate  # type: ignore
except Exception:
    def integrate(goal: str, plan: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore
        return plan

# plan/execute (myagko)
try:
    from modules.self.plan_orchestrator import plan, execute  # type: ignore
except Exception:
    def plan(goal: str, params: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore
        steps: List[Dict[str, Any]] = [{"kind": "echo", "msg": f"goal:{goal}"}]
        return {"goal": goal, "steps": steps}
    def execute(p: Dict[str, Any], safe: bool = True) -> Dict[str, Any]:  # type: ignore
        res = [{"ok": True, "step": s.get("kind", "echo")} for s in (p.get("steps") or [])]
        return {"ok": True, "results": res, "safe": bool(safe)}

# ---------------------------------------------------------------------------
# Lokalnoe sostoyanie dlya sovmestimosti s UI
# ---------------------------------------------------------------------------

def _lm_info() -> Dict[str, Any]:
    return {
        "base": os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
        "model": os.getenv("LMSTUDIO_CHAT_MODEL", "openai/gpt-oss-20b"),
    }

_THINKER_AB = (os.getenv("ESTER_THINKER_AB") or "A").strip().upper()

_STATE: Dict[str, Any] = {
    "running": False,
    "cycles": 0,
    "last_error": None,   # type: Optional[str]
    "last_reply": None,   # type: Optional[str]
    "interval_sec": 25,
    "ab": _THINKER_AB,
    "started_ts": None,   # type: Optional[int]
    "stopped_ts": None,   # type: Optional[int]
}

# ---------------------------------------------------------------------------
# Publichnye funktsii
# ---------------------------------------------------------------------------

def think(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params = params or {}
    p = plan(goal, params)
    p = integrate(goal, p)
    exe = execute(p, safe=True)
    summary = f"plan:{len(p.get('steps', []))}; dry-run:{len(exe.get('results', []))}"
    try:
        record_thought(goal=goal, conclusion=summary, success=True)
    except Exception:
        pass
    # sokhranyaem «posledniy otvet» v sostoyanii — eto chitaet UI
    _STATE["last_reply"] = summary
    return {"ok": True, "goal": goal, "summary": summary, "plan": p, "exec": exe}

class _ThinkerA:
    def think(self, goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return think(goal, params)
    def __call__(self, goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return self.think(goal, params)

class _ThinkerB(_ThinkerA):
    def think(self, goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        out = super().think(goal, params)
        if isinstance(out, dict):
            out["ab"] = "B"
        return out

def _make_thinker():
    try:
        return _ThinkerB() if _THINKER_AB == "B" else _ThinkerA()
    except Exception:
        return _ThinkerA()

THINKER = _make_thinker()

def start(goal: str = "heartbeat", interval_sec: int = 25, **params: Any) -> Dict[str, Any]:
    """
    Sovmestimaya s chat_routes signatura: start(interval_sec=?).
    Mozhno takzhe peredavat goal i proizvolnye dop.parametry.
    """
    _STATE["running"] = True
    _STATE["cycles"] = 0
    _STATE["last_error"] = None
    _STATE["interval_sec"] = int(interval_sec or 25)
    _STATE["started_ts"] = int(time.time())
    _STATE["stopped_ts"] = None
    # V «zakrytom» rezhime delaem tolko zapis v pamyat i bystryy dry-run
    res = think(goal, {"interval_sec": _STATE["interval_sec"], **params})
    return {
        "ok": True,
        "running": True,
        "cycles": _STATE["cycles"],
        "last_reply": _STATE["last_reply"],
        "lm": _lm_info(),
        "ab": _STATE["ab"],
        "started_ts": _STATE["started_ts"],
        "result": res,
    }

def stop(reason: str | None = None) -> Dict[str, Any]:
    _STATE["running"] = False
    _STATE["stopped_ts"] = int(time.time())
    return {
        "ok": True,
        "running": False,
        "cycles": _STATE["cycles"],
        "last_reply": _STATE["last_reply"],
        "lm": _lm_info(),
        "ab": _STATE["ab"],
        "stopped_ts": _STATE["stopped_ts"],
        "reason": reason or "manual",
    }

def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "running": bool(_STATE["running"]),
        "cycles": int(_STATE["cycles"]),
        "last_error": _STATE["last_error"],
        "last_reply": _STATE["last_reply"],
        "lm": _lm_info(),
        "ab": _STATE["ab"],
        "interval_sec": _STATE["interval_sec"],
        "started_ts": _STATE["started_ts"],
        "stopped_ts": _STATE["stopped_ts"],
        "ts": int(time.time()),
    }
