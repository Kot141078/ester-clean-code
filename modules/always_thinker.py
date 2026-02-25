# -*- coding: utf-8 -*-
"""modules/always_thinker.py - fonovyy myslitel Ester.

Mosty:
- Yavnyy: (CLI / scripts.thinkd_run ↔ Myshlenie) - tochka vkhoda dlya fonovogo myshleniya.
- Yavnyy: (volition_registry / will_scheduler_adapter ↔ cascade_closed) - ispolnyaet volevye impulsy.
- Yavnyy: (thought_trace_adapter ↔ Memory/Log) — formiruet chelovekochitaemyy treys.
- Skrytyy #1: (Prioritety ↔ Resursy) — planirovschik voli vybiraet vazhnye tseli.
- Skrytyy #2: (Kaskady ↔ Guard/Trace) — soblyudaet limity i ostavlyaet ponyatnyy sled.

Rezhimy:
- ESTER_VOLITION_MODE:
    A - volya vyklyuchena.
    B - impulsy prinimayutsya.
- ESTER_WILL_SCHED_AB:
    A - prostoy rezhim: berem sleduyuschiy impuls iz volition_registry i zapuskaem odin kaskad.
    B - expandednnyy: will_scheduler_adapter.process_next()
         (priority, mnogokontekst, guard), s bezopasnym otkatom.
- ESTER_TRACE_AB:
    A - add kratkiy trace_text for nalichii adaptera.
    B - add polnyy trace (struktura + tekst).

Zemnoy abzats:
    from modules import always_thinker
    always_thinker.start_background(interval_sec=15.0)
    # Demon chitaet impulsy i dumaet kaskadno, s ponyatnym sledom.
# c=a+b"""
from __future__ import annotations

import os
import threading
import time
import traceback
from typing import Any, Optional, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.thinking import volition_registry
except Exception:  # pragma: no cover
    volition_registry = None  # type: ignore

try:
    from modules.thinking import cascade_closed
except Exception:  # pragma: no cover
    cascade_closed = None  # type: ignore

try:
    from modules.thinking import will_scheduler_adapter as will_sched
except Exception:  # pragma: no cover
    will_sched = None  # type: ignore

try:
    from modules.thinking import thought_trace_adapter as tta
except Exception:  # pragma: no cover
    tta = None  # type: ignore

_thread: Optional[threading.Thread] = None
_stop_flag = threading.Event()


def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
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


def _volition_on() -> bool:
    mode = (os.environ.get("ESTER_VOLITION_MODE", "A") or "A").strip().upper()
    return mode == "B"


def _use_scheduler() -> bool:
    """Let's check if the extended will planner can be used."""
    mode = (os.environ.get("ESTER_WILL_SCHED_AB", "A") or "A").strip().upper()
    return (
        mode == "B"
        and will_sched is not None
        and hasattr(will_sched, "process_next")
    )


def _trace_mode() -> str:
    return (os.environ.get("ESTER_TRACE_AB", "A") or "A").strip().upper()


def _attach_trace_if_enabled(result: Dict[str, Any]) -> Dict[str, Any]:
    """Myagko dobavlyaet treys k rezultatu, esli vklyuchen ESTER_TRACE_AB i dostupen thought_trace_adapter.

    Nemenyaet kontrakt:
    - v rezhime A add tolko 'trace_text' (esli est);
    - v rezhime B addavlyaet polnuyu strukturu 'trace'."""
    mode = _trace_mode()
    if mode not in ("A", "B"):
        return result
    if not tta or not hasattr(tta, "from_cascade_result"):
        return result

    try:
        src = result.get("result")
        if not isinstance(src, dict):
            src = result
        trace = tta.from_cascade_result(src)
        if not isinstance(trace, dict) or not trace.get("ok"):
            return result

        if mode == "B":
            result.setdefault("trace", trace)
        else:
            txt = trace.get("text")
            if txt:
                result.setdefault("trace_text", txt)
    except Exception:
        # The trace should never break the main thread.
        pass

    return result


def _process_once_simple() -> Dict[str, Any]:
    """Easy mode:
    - takes the next impulse from the Volition_Register;
    - launches cascade_closed.run_cascade;
    - optionally adds a trace."""
    if not _volition_on():
        return {"ok": True, "processed": False, "note": "volition disabled"}

    if not (volition_registry and hasattr(volition_registry, "get_next_impulse")):
        return {"ok": False, "processed": False, "error": "volition_registry not available"}

    imp = volition_registry.get_next_impulse()
    if not imp:
        return {"ok": True, "processed": False, "note": "no impulse"}

    goal = imp.get("goal") or "(unknown target)"

    if not (cascade_closed and hasattr(cascade_closed, "run_cascade")):
        return {"ok": False, "processed": False, "goal": goal, "error": "cascade_closed not available"}

    try:
        casc = cascade_closed.run_cascade(goal)
        res: Dict[str, Any] = {
            "ok": True,
            "processed": True,
            "goal": goal,
            "summary": casc.get("summary", ""),
            "result": casc,
        }
        try:
            _mirror_background_event(
                f"[ALWAYS_THINKER] goal={goal} summary={str(casc.get('summary', ''))[:300]}",
                "always_thinker",
                "processed",
            )
        except Exception:
            pass
        return _attach_trace_if_enabled(res)
    except Exception as e:
        traceback.print_exc()
        try:
            _mirror_background_event(
                f"[ALWAYS_THINKER_ERROR] goal={goal} err={e}",
                "always_thinker",
                "error",
            )
        except Exception:
            pass
        return {"ok": False, "processed": False, "goal": goal, "error": str(e)}


def _process_once_scheduled() -> Dict[str, Any]:
    """Advanced Mode:
    - uses will_scheduler_adapter.process_next();
    - optionally adds a trace;
    - in case of an error, rollback to simple mode."""
    if not _volition_on():
        return {"ok": True, "processed": False, "skipped": True, "reason": "volition disabled"}

    if not _use_scheduler():
        return _process_once_simple()

    try:
        res = will_sched.process_next()
        if not isinstance(res, Dict):
            try:
                _mirror_background_event(
                    "[ALWAYS_THINKER_SCHED_ERROR] scheduler returned non-dict",
                    "always_thinker",
                    "scheduler_error",
                )
            except Exception:
                pass
            return {"ok": False, "processed": False, "error": "scheduler returned non-dict"}
        try:
            if res.get("processed"):
                goal = str(res.get("goal") or "")
                summary = str(res.get("summary") or "")[:300]
                _mirror_background_event(
                    f"[ALWAYS_THINKER] goal={goal} summary={summary}",
                    "always_thinker",
                    "processed",
                )
        except Exception:
            pass
        return _attach_trace_if_enabled(res)
    except Exception as e:
        traceback.print_exc()
        try:
            _mirror_background_event(
                f"[ALWAYS_THINKER_SCHED_ERROR] {e}",
                "always_thinker",
                "scheduler_error",
            )
        except Exception:
            pass
        fb = _process_once_simple()
        fb["scheduler_error"] = str(e)
        return _attach_trace_if_enabled(fb)


def _worker_loop(interval_sec: float) -> None:
    """Tsikl fonovogo myslitelya.

    Logika:
    - Esli vklyuchen rashirennyy planirovschik — ispolzuem ego.
    - Inache - prostoy rezhim volition_registry + cascade_closed.
    - Lyubye oshibki logiruyutsya i ne ronyayut protsess."""
    while not _stop_flag.is_set():
        try:
            if _use_scheduler():
                _process_once_scheduled()
            else:
                _process_once_simple()
            time.sleep(interval_sec if interval_sec > 0 else 1.0)
        except Exception:
            traceback.print_exc()
            try:
                _mirror_background_event(
                    "[ALWAYS_THINKER_LOOP_ERROR]",
                    "always_thinker",
                    "loop_error",
                )
            except Exception:
                pass
            time.sleep(1.0)


def start_background(interval_sec: float = 5.0) -> Dict[str, Any]:
    """Zapustit fonovogo myslitelya.

    Drop-in:
    - ispolzuetsya scripts/thinkd.py or scripts/thinkd_run.py;
    - uchityvaet A/B-flagi dlya voli, planirovschika i treysa;
    - ne menyaet vneshnie HTTP/JSON kontrakty."""
    global _thread
    if _thread and _thread.is_alive():
        return {"ok": False, "running": True, "note": "already running"}
    _stop_flag.clear()
    _thread = threading.Thread(target=_worker_loop, args=(interval_sec,), daemon=True)
    _thread.start()
    try:
        _mirror_background_event(
            f"[ALWAYS_THINKER_START] interval={interval_sec}",
            "always_thinker",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "running": True, "interval_sec": interval_sec}


def consume_once() -> Dict[str, Any]:
    """Obrabotat odin shag myshleniya (ruchnoy smoke-test).

    - Esli vklyuchen rashirennyy planirovschik — ispolzuetsya on.
    - Inache - prostoy rezhim.
    - V oboikh sluchayakh myagko dobavlyaet treys, esli vklyuchen."""
    try:
        if _use_scheduler():
            return _process_once_scheduled()
        return _process_once_simple()
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "processed": False, "error": str(e)}


def stop_background() -> Dict[str, Any]:
    """Request background thinker to stop."""
    _stop_flag.set()
    try:
        _mirror_background_event(
            "[ALWAYS_THINKER_STOP]",
            "always_thinker",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, "stopped": True}