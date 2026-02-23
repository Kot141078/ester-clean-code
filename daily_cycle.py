# -*- coding: utf-8 -*-
"""
modules/memory/daily_cycle.py — nochnoy tsikl «gigieny pamyati» Ester (FinalBridge).

Izmenenie:
- Pered vyzovom experience.sync_experience(mode="sleep") peredaem tekuschiy
  rezultat tsikla cherez experience.set_last_sleep_status(res).
- Eto ustranyaet gonku: sloy opyta vsegda vidit svezhie summary/reflection.

Ostalnoe povedenie i signatury bez izmeneniy.
"""
from __future__ import annotations

from typing import Dict, Any, Callable
import os
import time
import traceback

from modules.memory.events import record_event  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import summary  # type: ignore
except Exception:
    summary = None  # type: ignore

try:
    from modules.memory import qa  # type: ignore
except Exception:
    qa = None  # type: ignore

try:
    from modules.memory import policies  # type: ignore
except Exception:
    policies = None  # type: ignore

try:
    from modules.memory import backups  # type: ignore
except Exception:
    backups = None  # type: ignore

try:
    from modules.memory import reflection  # type: ignore
except Exception:
    reflection = None  # type: ignore

try:
    from modules.memory import experience  # type: ignore
except Exception:
    experience = None  # type: ignore


AB_ENV = "ESTER_MEMORY_SLEEP_AB"
QA_ENV = "ESTER_MEMORY_SLEEP_QA"
POLICY_ENV = "ESTER_MEMORY_SLEEP_POLICY"
BACKUP_ENV = "ESTER_MEMORY_SLEEP_BACKUP"
REFLECT_ENV = "ESTER_MEMORY_REFLECT"
EXPERIENCE_IN_SLEEP_ENV = "ESTER_MEMORY_EXPERIENCE_IN_SLEEP"

_LAST_RESULT: Dict[str, Any] = {}


def _slot() -> str:
    v = (os.getenv(AB_ENV) or "A").strip().upper()
    return "B" if v == "B" else "A"


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on", "b")


def status() -> Dict[str, Any]:
    slot = _slot()
    if not _LAST_RESULT:
        return {
            "ok": True,
            "slot": slot,
            "last_run_ts": 0,
            "have_result": False,
        }

    out = dict(_LAST_RESULT)
    out.setdefault("slot", slot)
    out["ok"] = bool(out.get("ok", True))
    out["have_result"] = True
    return out


def _run_step(res: Dict[str, Any], name: str, fn: Callable[[], Any]) -> None:
    try:
        info = fn()
        step_ok = bool(info.get("ok", True)) if isinstance(info, dict) else True
        res.setdefault("steps", []).append(
            {"step": name, "ok": step_ok, "info": info}
        )
        if not step_ok:
            res["ok"] = False
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc(limit=3)
        res.setdefault("steps", []).append(
            {"step": name, "ok": False, "error": str(e), "trace": tb}
        )
        res["ok"] = False


def run_cycle(mode: str = "auto") -> Dict[str, Any]:
    global _LAST_RESULT

    start_ts = int(time.time())
    slot = _slot()
    res: Dict[str, Any] = {
        "ok": True,
        "slot": slot,
        "started_ts": start_ts,
        "mode": (mode or "auto"),
        "steps": [],
    }

    # 1) Svodka dnya
    if summary is not None and hasattr(summary, "generate_summary"):
        def _s():
            return summary.generate_summary("day")  # type: ignore[attr-defined]
        _run_step(res, "summary_day", _s)

    # 2) QA (B / po flagu)
    if qa is not None and hasattr(qa, "run_full_qc"):
        if _bool_env(QA_ENV, default=(slot == "B")):
            def _qa():
                return qa.run_full_qc(auto_fix=(slot == "B"))  # type: ignore[attr-defined]
            _run_step(res, "memory_qa", _qa)

    # 3) Politiki (po flagu)
    if policies is not None and hasattr(policies, "automod_tick"):
        if _bool_env(POLICY_ENV, default=False):
            def _pol():
                report: Dict[str, Any] = {
                    "automod": policies.automod_tick(),  # type: ignore[attr-defined]
                }
                if hasattr(policies, "compact"):
                    dry_run = (slot == "A")
                    report["compact"] = policies.compact(dry_run=dry_run)  # type: ignore[attr-defined]
                return {"ok": True, "report": report}
            _run_step(res, "memory_policies", _pol)

    # 4) Bekap (B / po flagu)
    if backups is not None and hasattr(backups, "create_backup"):
        if _bool_env(BACKUP_ENV, default=(slot == "B")):
            def _bk():
                label = f"sleep_{start_ts}"
                bk = backups.create_backup(label)  # type: ignore[attr-defined]
                return {"ok": True, "backup": bk}
            _run_step(res, "memory_backup", _bk)

    # 5) Refleksiya (po umolchaniyu vklyuchena)
    if reflection is not None and hasattr(reflection, "run_daily_reflection"):
        if _bool_env(REFLECT_ENV, default=True):
            def _rf():
                return reflection.run_daily_reflection(mode=res.get("mode", "auto"))  # type: ignore[attr-defined]
            _run_step(res, "daily_reflection", _rf)

    # Publikuem tekuschiy rezultat v oba sloya: status sna i modul opyta.
    try:
        _LAST_RESULT = dict(res)
    except Exception:
        _LAST_RESULT = res

    try:
        if experience is not None and hasattr(experience, "set_last_sleep_status"):
            experience.set_last_sleep_status(res)  # type: ignore[attr-defined]
    except Exception:
        # eto dopolnitelnyy most, ne kritichno
        pass

    # 6) Opyt (po flagu)
    if experience is not None and hasattr(experience, "sync_experience"):
        if _bool_env(EXPERIENCE_IN_SLEEP_ENV, default=False):
            def _ex():
                return experience.sync_experience(mode="sleep")  # type: ignore[attr-defined]
            _run_step(res, "experience_sync", _ex)

    # 7) Log tsikla
    try:
        record_event(
            kind="sleep_cycle",
            op="run_cycle",
            ok=bool(res.get("ok", True)),
            info={
                "slot": slot,
                "mode": res.get("mode"),
                "steps": [
                    {"step": s.get("step"), "ok": bool(s.get("ok", True))}
                    for s in res.get("steps", [])
                ],
            },
        )
    except Exception:
        pass

    res["finished_ts"] = int(time.time())
    _LAST_RESULT = res
    return res


def build_daily_narrative(summary: dict | None, insights: list[dict] | None) -> str:
    """
    Formiruet korotkiy chelovekochitaemyy tekst-refleksiyu dnya na osnove svodki
    i spiska insaytov. Bezopasno k otsutstvuyuschim polyam.
    """
    try:
        parts: list[str] = []
        if summary and isinstance(summary, dict):
            text = (summary.get("text") or "").strip()
            meta = summary.get("meta") or {}
            emo = meta.get("emo")
            types = meta.get("types") or {}
            total = 0
            if isinstance(types, dict):
                total = sum(int(v) for v in types.values() if isinstance(v, (int, float)))
            # Pervoe predlozhenie
            if total:
                mood = "polozhitelnoe" if (emo or 0) > 0 else ("otritsatelnoe" if (emo or 0) < 0 else "neytralnoe")
                parts.append(f"Segodnya bylo zapisey: {total}; nastroenie v tselom {mood}.")
            if text:
                parts.append(text)
            # Temy
            terms = meta.get("terms") or []
            if isinstance(terms, list) and terms:
                top = ", ".join(map(str, terms[:5]))
                parts.append(f"Glavnye temy: {top}.")
        # Insayty
        if insights and isinstance(insights, list):
            titles = [str(i.get("title") or "").strip() for i in insights if isinstance(i, dict)]
            titles = [t for t in titles if t]
            if titles:
                bullets = "; ".join(titles[:3])
                parts.append(f"Vyvody dnya: {bullets}.")
        return " ".join(p for p in parts if p).strip()
    except Exception:
        return ""