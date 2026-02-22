# -*- coding: utf-8 -*-
"""
modules/cron/orchestrator.py — nochnoy orkestrator: heal→compact→snapshot→reindex→health→binders→backup→otchet.

Mosty:
- Yavnyy: (Memory/Indeksy/AB/Binders/Backups ↔ Cron) edinaya protsedura, odin otchet.
- Skrytyy #1: (Passport ↔ Prozrachnost) vse shagi shtampuyutsya s dlitelnostyu/rezultatom.
- Skrytyy #2: (Guard/RBAC ↔ Bezopasnost) posledovatelnye vyzovy, uvazhenie guard, legkie health-pingi.

Zemnoy abzats:
Kak nochnoy tekhprotsess v tsekhu: smazali stanki, podtyanuli remni, snyali kopiyu sklada i proverili pozharnuyu signalizatsiyu — k utru vse gotovo rabotat.

# c=a+b
"""
from __future__ import annotations
import os, time, json, threading, urllib.request, urllib.error, datetime, hashlib, zipfile
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AUTORUN = (os.getenv("CRON_AUTORUN","true").lower()=="true")
RUN_AT  = os.getenv("CRON_TIME","03:17").strip()   # HH:MM
TZ      = os.getenv("CRON_TZ","UTC")
HEALTHS = [p.strip() for p in (os.getenv("CRON_HEALTH_PATHS","/app/discover/status,/self/capmap,/runtime/ab/health").split(",")) if p.strip()]
REPORT_DIR = os.getenv("CRON_REPORT_DIR","data/cron/reports")
RESPECT_GUARD = (os.getenv("CRON_RESPECT_GUARD","true").lower()=="true")

os.makedirs(REPORT_DIR, exist_ok=True)

_state={"enabled": AUTORUN, "time": RUN_AT, "tz": TZ, "last_t": 0, "last_report": "", "next_t": 0, "loop":"idle"}

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

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "cron://nightly")
    except Exception:
        pass

def _call_json(path: str, payload: dict|None=None, timeout: int=60)->Tuple[bool, Any]:
    url="http://127.0.0.1:8000"+path
    try:
        if payload is None:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return True, json.loads(r.read().decode("utf-8"))
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return False, {"error": str(e), "path": path}

def _sleep_ms(ms: int):
    time.sleep(max(0.0, ms/1000.0))

def _health_block(tag: str)->Dict[str,Any]:
    results=[]
    for p in HEALTHS:
        ok, rep=_call_json(p, None, 20)
        results.append({"path": p, "ok": bool(ok and (isinstance(rep, dict) and rep.get("ok", True)))})
        _sleep_ms(100 if RESPECT_GUARD else 0)
    all_ok=all(r["ok"] for r in results) if results else True
    _passport("cron_health", {"tag": tag, "ok": all_ok, "n": len(results)})
    return {"ok": all_ok, "results": results}

def _best_effort(paths: List[Tuple[str, dict|None, int]])->List[Dict[str,Any]]:
    out=[]
    for path, payload, timeout in paths:
        ok, rep=_call_json(path, payload, timeout)
        out.append({"path": path, "ok": ok and (isinstance(rep, dict) and rep.get("ok", True)), "rep": rep})
        _sleep_ms(200 if RESPECT_GUARD else 0)
    return out

def _now_local()->datetime.datetime:
    # bez storonnikh zavisimostey: ispolzuem lokalnoe vremya khosta kak UTC po umolchaniyu
    return datetime.datetime.now()

def _next_epoch()->int:
    hh,mm=[int(x) for x in (RUN_AT.split(":")+["0"])[:2]]
    now=_now_local()
    target=now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target = target + datetime.timedelta(days=1)
    return int(target.timestamp())

def status()->Dict[str,Any]:
    _state["next_t"]=_next_epoch()
    return {"ok": True, "state": dict(_state)}

def config(enable: bool|None=None, time_hhmm: str|None=None, tz: str|None=None)->Dict[str,Any]:
    if enable is not None: 
        _state["enabled"]=bool(enable)
    if time_hhmm:
        hhmm=time_hhmm.strip()
        if len(hhmm)>=4 and ":" in hhmm:
            _state["time"]=hhmm
            os.environ["CRON_TIME"]=hhmm
    if tz:
        _state["tz"]=tz
        os.environ["CRON_TZ"]=tz
    return status()

def _report_path(ts: int)->str:
    return os.path.join(REPORT_DIR, f"nightly_{ts}.json")

def run_nightly(dry_run: bool=False)->Dict[str,Any]:
    t0=time.time(); steps=[]
    try:
        _mirror_background_event(
            f"[CRON_NIGHTLY_START] dry_run={int(bool(dry_run))}",
            "cron_nightly",
            "start",
        )
    except Exception:
        pass
    # 0) Health (pre)
    steps.append({"pre_health": _health_block("before")})
    if dry_run:
        rep={"ok": True, "dry_run": True, "steps": steps}
        return rep
    # 1) Heal/compact/snapshot pamyati (best-effort, esli ruchek net — propuskaem)
    steps.append({"mem_heal":     _best_effort([("/mem/heal", {}, 120)])})
    steps.append({"mem_compact":  _best_effort([("/mem/compact", {}, 120)])})
    steps.append({"mem_snapshot": _best_effort([("/mem/snapshot", {}, 120)])})
    # 2) Reindex (gibrid/ierarkhiya)
    steps.append({"rag_reindex":  _best_effort([("/rag/reindex", {}, 180)])})
    # 3) AB-slot health
    steps.append({"ab_health":    _best_effort([("/runtime/ab/health", {}, 30)])})
    # 4) Binders (STT/media i dr., esli podklyucheny)
    steps.append({"bind_stt":     _best_effort([("/bind/stt/run", {}, 600)])})
    # 5) Backup snapshot (ZIP + manifest)
    ok, b1=_call_json("/backup/snapshot", {"label": "nightly"}, 600)
    steps.append({"backup_snapshot": {"ok": ok and (isinstance(b1, dict) and b1.get("ok", True)), "rep": b1}})
    ok2, b2=_call_json("/backup/status", None, 20)
    steps.append({"backup_status": {"ok": ok2 and (isinstance(b2, dict) and b2.get("ok", True)), "rep": b2}})
    # 6) Health (post)
    steps.append({"post_health": _health_block("after")})
    # final
    t1=time.time()
    report={"t_start": int(t0), "t_end": int(t1), "dur_s": round(t1-t0,2), "steps": steps}
    rp=_report_path(int(t0))
    try:
        os.makedirs(REPORT_DIR, exist_ok=True)
        open(rp,"w",encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=2))
        _state["last_report"]=rp
        _state["last_t"]=int(t1)
    except Exception:
        pass
    _passport("cron_nightly", {"dur_s": report["dur_s"]})
    try:
        _mirror_background_event(
            f"[CRON_NIGHTLY_DONE] dur_s={report['dur_s']} report={rp}",
            "cron_nightly",
            "done",
        )
    except Exception:
        pass
    return {"ok": True, "report": rp, "dur_s": report["dur_s"]}

def _loop():
    while True:
        _state["loop"]="sleeping"
        if not _state["enabled"]:
            time.sleep(1); continue
        nxt=_next_epoch(); _state["next_t"]=nxt
        now=int(time.time())
        if now>=nxt:
            _state["loop"]="running"
            try:
                run_nightly(False)
            except Exception:
                try:
                    _mirror_background_event(
                        "[CRON_NIGHTLY_ERROR]",
                        "cron_nightly",
                        "error",
                    )
                except Exception:
                    pass
                pass
            _state["loop"]="sleeping"
            # chtoby ne zatsiklitsya, zhdem minutu
            time.sleep(60)
        else:
            time.sleep(min(30, max(1, nxt-now)))

if AUTORUN:
    th=threading.Thread(target=_loop, name="cron_orchestrator", daemon=True)
    th.start()
    _passport("cron_thread", {"started": True})
    try:
        _mirror_background_event(
            "[CRON_ORCH_START]",
            "cron_nightly",
            "start",
        )
    except Exception:
        pass
# c=a+b