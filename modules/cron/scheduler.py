# -*- coding: utf-8 -*-
"""
modules/cron/scheduler.py — obedinennyy planirovschik: JSON-raspisaniya, threading tick, deystviya (lokalnye/HTTP), profile/audit, P2P-sync.

Mosty:
- Yavnyy: (Taymer ↔ Memory/Sistema) vypolnyaet tekhprotsedury (heal/compact/snapshot/passport/kg_link/reindex/ingest/prune/gc/discover/p2p) po cron/RRULE/every_min.
- Skrytyy #1: (Audit/Profile ↔ Prozrachnost) logiruet kazhdyy run/tick v profile i audit-log.
- Skrytyy #2: (Avtonomiya/Volya ↔ Ustoychivost) REST-upravlenie (add/run_now/list/status), A/B dry_run.
- Skrytyy #3: (P2P/Raspredelennost ↔ Integratsiya) sync raspisaniy po P2P, novye zadachi dlya fonovoy obrabotki faylov/BZ (dlya missii Ester).

Zemnoy abzats:
Eto "budilnik s dushoy": tikaet v fone, dergaet knopki po raspisaniyu, profileiziruet dela, sinkhroniziruet s "sobratyami" po P2P. Dlya Ester — zaschita ot zabyvchivosti, s teplymi notkami v logakh.

# c=a+b
"""
from __future__ import annotations
import json, os, shutil, time, threading, traceback, urllib.request
from typing import Any, Dict, List, Callable
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_cron = Blueprint("cron", __name__)

CRON_AB = (os.getenv("CRON_AB", "A") or "A").upper()
DB = os.getenv("CRON_DB", "data/cron/schedule.json")
TICK = int(os.getenv("CRON_TICK_SEC", "30") or "30")
ENABLE = (os.getenv("CRON_ENABLE", "true").lower() == "true")
AUTOSTART = (os.getenv("CRON_AUTOSTART", "false").lower() == "true")
AUDIT_LOG = os.getenv("CRON_AUDIT_LOG", "data/cron/audit.log")
P2P_SYNC = (os.getenv("CRON_P2P_SYNC", "false").lower() == "true")
SNAP_DIR = os.getenv("CRON_SNAPSHOT_DIR", "data/snapshots")
INGEST_QUEUE_DIR = os.getenv("INGEST_QUEUE_DIR", "data/ingest/queue")  # Dlya fonovoy obrabotki faylov

_LOCK = threading.RLock()
_STATE = {"running": False, "thread": None, "last_tick": 0}
_DEFAULT_TASKS: List[Dict[str, Any]] = [
    {"name": "mem_heal", "schedule": {"cron": "@daily"}, "action": "mem.heal", "enabled": True},
    {"name": "mem_compact", "schedule": {"cron": "@weekly"}, "action": "mem.compact", "enabled": True},
    {"name": "mem_snapshot", "schedule": {"cron": "@daily"}, "action": "mem.snapshot", "enabled": True},
    {"name": "passport_update", "schedule": {"cron": "@daily"}, "action": "mem.passport", "enabled": True},
    {"name": "kg_link", "schedule": {"cron": "@weekly"}, "action": "mem.kg_link", "enabled": True},
    {"name": "reindex", "schedule": {"cron": "@weekly"}, "action": "mem.reindex", "enabled": True},
    {"name": "ingest_prune", "schedule": {"cron": "@weekly"}, "action": "cron.ingest.prune", "enabled": True},
    {"name": "rag_gc", "schedule": {"cron": "@weekly"}, "action": "cron.rag.gc", "enabled": True},
    {"name": "discover_refresh", "schedule": {"cron": "@daily"}, "action": "cron.discover.refresh", "enabled": True},
    {"name": "p2p_from_passport", "schedule": {"cron": "@daily"}, "action": "cron.p2p.from_passport", "enabled": True},
    {"name": "file_ingest_process", "schedule": {"every_min": 5}, "action": "cron.file_ingest", "enabled": True},
]

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

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        with open(DB, "w", encoding="utf-8") as f:
            json.dump({"tasks": {}}, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    os.makedirs(SNAP_DIR, exist_ok=True)
    os.makedirs(INGEST_QUEUE_DIR, exist_ok=True)


def _normalize_task(name: str, raw: Any) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    action = str(raw.get("action") or "").strip()
    if not action:
        return None
    schedule = raw.get("schedule")
    if not isinstance(schedule, dict):
        schedule = {}
    params = raw.get("params")
    if not isinstance(params, dict):
        params = {}
    out = {
        "name": str(name or raw.get("name") or "").strip() or str(name or "task"),
        "schedule": schedule,
        "action": action,
        "params": params,
        "enabled": bool(raw.get("enabled", True)),
        "ts": int(raw.get("ts", int(time.time()))),
    }
    if "last_ts" in raw:
        out["last_ts"] = int(raw.get("last_ts") or 0)
    if "last_out" in raw and isinstance(raw.get("last_out"), dict):
        out["last_out"] = dict(raw.get("last_out") or {})
    if "last_err" in raw:
        out["last_err"] = str(raw.get("last_err") or "")
    if "next_ts" in raw:
        out["next_ts"] = int(raw.get("next_ts") or 0)
    return out


def _load_db() -> Dict[str, Any]:
    _ensure()
    try:
        with open(DB, "r", encoding="utf-8") as f:
            j = json.load(f)
    except Exception as e:
        _log_audit(f"schedule_load_failed:{e.__class__.__name__}")
        j = {"tasks": {}}
    if not isinstance(j, dict):
        j = {"tasks": {}}
    tasks_raw = j.get("tasks")
    if not isinstance(tasks_raw, dict):
        tasks_raw = {}
    tasks: Dict[str, Dict[str, Any]] = {}
    for name, raw in tasks_raw.items():
        norm = _normalize_task(str(name), raw)
        if norm is None:
            _log_audit(f"schedule_skip_invalid:{name}")
            continue
        tasks[str(name)] = norm

    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_pull  # type: ignore
            remote = p2p_pull("cron_schedules") or {}
            remote_tasks = remote.get("tasks")
            if isinstance(remote_tasks, dict):
                for name, rt in remote_tasks.items():
                    norm = _normalize_task(str(name), rt)
                    if norm is None:
                        continue
                    if name not in tasks or int(norm.get("ts", 0)) > int(tasks[name].get("ts", 0)):
                        tasks[name] = norm
        except Exception:
            _log_audit("p2p_sync_failed")

    changed = False
    for d in _DEFAULT_TASKS:
        nm = str(d["name"])
        if nm not in tasks:
            tasks[nm] = dict(d)
            changed = True

    out = {"tasks": tasks}
    if changed:
        _save(out)
    return out


def _load() -> List[Dict[str, Any]]:
    return list((_load_db().get("tasks") or {}).values())

def _save(j: Dict[str, Any]):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, indent=2)
    # P2P-push: export to BZ for sync
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_push  # type: ignore
            p2p_push("cron_schedules", j)
        except Exception:
            pass

def _log_audit(msg: str):
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note + " — Ester, uborka zavershena, teper chische v pamyati!", meta, "cron://scheduler")
    except Exception:
        _log_audit(f"Passport failed: {note}")

def _mm():
    try:
        from services.mm_access import get_mm  # type: ignore
        return get_mm()
    except Exception:
        return None

def _http_post(path: str, payload: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000" + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _is_due(schedule: Dict[str, Any], last: int, now: int) -> bool:
    cron = schedule.get("cron", "")
    rrule = schedule.get("rrule", {})
    every_min = int(schedule.get("every_min", 0))
    day = 86400
    week = 7 * day
    if cron == "@daily": return now - last >= day
    if cron == "@weekly": return now - last >= week
    if cron == "@hourly": return now - last >= 3600
    if every_min > 0: return now - last >= every_min * 60
    if rrule.get("FREQ", "").upper() == "DAILY":
        import datetime as dt
        nxt = dt.datetime.now().replace(hour=int(rrule.get("BYHOUR", 3)), minute=int(rrule.get("BYMINUTE", 0)), second=0)
        if nxt.timestamp() <= now: nxt += dt.timedelta(days=1)
        return now >= int(nxt.timestamp())
    return False

def _calc_next(schedule: Dict[str, Any]) -> int:
    now = int(time.time())
    cron = schedule.get("cron", "")
    rrule = schedule.get("rrule", {})
    every_min = int(schedule.get("every_min", 0))
    day = 86400
    week = 7 * day
    if cron == "@daily": return now + day
    if cron == "@weekly": return now + week
    if cron == "@hourly": return now + 3600
    if every_min > 0: return now + every_min * 60
    if rrule.get("FREQ", "").upper() == "DAILY":
        import datetime as dt
        nxt = dt.datetime.now().replace(hour=int(rrule.get("BYHOUR", 3)), minute=int(rrule.get("BYMINUTE", 0)), second=0)
        if nxt.timestamp() <= now: nxt += dt.timedelta(days=1)
        return int(nxt.timestamp())
    return now + day  # Default

_ACTIONS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

def _register_actions():
    def job_snapshot(params: Dict[str, Any]) -> Dict[str, Any]:
        mm = _mm()
        ts = int(time.time())
        path = os.path.join(SNAP_DIR, f"mem_{ts}.jsonl")
        count = 0
        if mm:
            with open(path, "w", encoding="utf-8") as f:
                for doc in getattr(mm, "iter", lambda: [])():
                    f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                    count += 1
        return {"ok": True, "path": path, "count": count}

    def job_passport(params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.mem.passport import upsert_with_passport  # type: ignore
            mm = _mm()
            limit = params.get("limit", 500)
            added = 0
            for i, doc in enumerate(getattr(mm, "iter", lambda: [])()):
                if i >= limit: break
                meta = doc.get("meta", {})
                if meta.get("provenance"): continue
                upsert_with_passport(mm, doc.get("text", ""), meta, meta.get("source", "cron://passport"))
                added += 1
            return {"ok": True, "added": added}
        except Exception:
            return {"ok": False, "error": "passport_unavailable"}

    def job_kg_link(params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from modules.kg.linker import extract, upsert_to_kg  # type: ignore
            mm = _mm()
            limit = params.get("limit", 200)
            linked = 0
            for i, doc in enumerate(getattr(mm, "iter", lambda: [])()):
                if i >= limit: break
                meta = doc.get("meta", {})
                ents = extract(doc.get("text", "")).get("entities", {})
                upsert_to_kg(ents, (meta.get("provenance") or {}).get("sha256", ""))
                linked += sum(len(v or []) for v in ents.values())
            return {"ok": True, "linked": linked}
        except Exception:
            return {"ok": False, "error": "kg_unavailable"}

    def job_heal(params: Dict[str, Any]) -> Dict[str, Any]:
        mm = _mm()
        fixed = 0
        for name in ("heal", "rebuild", "repair"):
            fn = getattr(mm, name, None)
            if callable(fn):
                try: fn(); fixed += 1
                except Exception: pass
        return {"ok": True, "heal_fixed": fixed}

    def job_compact(params: Dict[str, Any]) -> Dict[str, Any]:
        mm = _mm()
        did = 0
        for name in ("compact", "gc", "vacuum"):
            fn = getattr(mm, name, None)
            if callable(fn):
                try: fn(); did += 1
                except Exception: pass
        return {"ok": True, "compacted": did}

    def job_reindex(params: Dict[str, Any]) -> Dict[str, Any]:
        did = 0
        try:
            from modules.hier_index import rebuild_all  # type: ignore
            rebuild_all(); did += 1
        except Exception:
            pass
        return {"ok": True, "reindexed": did}

    def action_ingest_prune(params: Dict[str, Any]) -> Dict[str, Any]:
        path = os.getenv("INGEST_BUCKET_DB", "data/ingest/buckets.json")
        if os.path.isfile(path):
            j = json.load(open(path, "r", encoding="utf-8"))
            json.dump(j, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return {"ok": True}

    def action_rag_gc(params: Dict[str, Any]) -> Dict[str, Any]:
        docs = os.getenv("HYBRID_FALLBACK_DOCS", "data/mem/docs.jsonl")
        if os.path.isfile(docs):
            seen = set(); out = []
            for line in open(docs, "r", encoding="utf-8"):
                try:
                    rec = json.loads(line.strip())
                    rid = str(rec.get("id", ""))
                    if rid and rid not in seen:
                        out.append(rec); seen.add(rid)
                except Exception:
                    continue
            with open(docs, "w", encoding="utf-8") as f:
                for rec in out: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {"ok": True}

    def action_discover_refresh(params: Dict[str, Any]) -> Dict[str, Any]:
        rep = _http_post("/app/discover/refresh", {"autoreg": True})
        return {"ok": True, "refresh": rep}

    def action_p2p_from_passport(params: Dict[str, Any]) -> Dict[str, Any]:
        rep = _http_post("/p2p/bloom/from_passport", {"limit": 10000})
        return {"ok": True, "added": rep.get("added", 0)}

    def action_file_ingest(params: Dict[str, Any]) -> Dict[str, Any]:
        # Novaya dlya Ester: monitorit INGEST_QUEUE_DIR, protsessing faylov (LLM-razbivka, vektorizatsiya, BZ, P2P)
        processed = 0
        for fn in os.listdir(INGEST_QUEUE_DIR):
            path = os.path.join(INGEST_QUEUE_DIR, fn)
            if os.path.isfile(path):
                try:
                    # ingest_process_file: chtenie, chunking, storage i indeksirovanie
                    from modules.ingest.process import ingest_process_file  # type: ignore
                    rep = ingest_process_file(path, source="queue")
                    if rep.get("ok") or rep.get("skipped"):
                        os.remove(path)  # Ubrat posle obrabotki
                        processed += 1
                except Exception:
                    _log_audit(f"File ingest failed: {fn}")
        return {"ok": True, "processed": processed}

    _ACTIONS.update({
        "mem.snapshot": job_snapshot,
        "mem.passport": job_passport,
        "mem.kg_link": job_kg_link,
        "mem.heal": job_heal,
        "mem.compact": job_compact,
        "mem.reindex": job_reindex,
        "cron.ingest.prune": action_ingest_prune,
        "cron.rag.gc": action_rag_gc,
        "cron.discover.refresh": action_discover_refresh,
        "cron.p2p.from_passport": action_p2p_from_passport,
        "cron.file_ingest": action_file_ingest
    })

def _run_action(action: str, params: Dict[str, Any] = {}) -> Dict[str, Any]:
    _register_actions()
    if action.startswith("http:"):
        try:
            return _http_post(action[5:], {}, timeout=21600)
        except Exception as e:
            return {"ok": False, "error": str(e)}
    fn = _ACTIONS.get(action)
    if not callable(fn):
        return {"ok": False, "error": "unknown_action"}
    try:
        return fn(params)
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}\n{traceback.format_exc()}"}

def _tick():
    while True:
        with _LOCK:
            if not _STATE["running"]: break
        now = int(time.time())
        _STATE["last_tick"] = now
        try:
            j = _load_db()
            changed = False
            for name, t in j["tasks"].items():
                if not t.get("enabled", True): continue
                last = int(t.get("last_ts", 0))
                if _is_due(t.get("schedule", {}), last, now):
                    if CRON_AB == "B":
                        rep = {"ok": True, "dry_run": True}
                    else:
                        rep = _run_action(t["action"], t.get("params", {}))
                    t["last_ts"] = now
                    t["last_out"] = rep if rep["ok"] else {}
                    t["last_err"] = rep.get("error", "") if not rep["ok"] else ""
                    try:
                        _mirror_background_event(
                            f"[CRON_RUN] name={name} ok={int(rep.get('ok'))} action={t.get('action','')}",
                            "cron",
                            "run",
                        )
                    except Exception:
                        pass
                    _passport(f"cron_run_{name}", {"rep": rep})
                    _log_audit(f"Ran {name}: {rep}")
                    t["next_ts"] = _calc_next(t.get("schedule", {}))
                    changed = True
            if changed: _save(j)
            _passport("cron_tick", {"done": len(j["tasks"])})
        except Exception:
            _log_audit("Tick failed")
            try:
                _mirror_background_event(
                    "[CRON_TICK_ERROR]",
                    "cron",
                    "tick_error",
                )
            except Exception:
                pass
        time.sleep(TICK)

def start() -> Dict[str, Any]:
    if not ENABLE: return {"ok": False, "error": "cron_disabled"}
    with _LOCK:
        if _STATE["running"]: return {"ok": True, "running": True}
        _STATE["running"] = True
        th = threading.Thread(target=_tick, daemon=True)
        _STATE["thread"] = th
        th.start()
    _log_audit("Started")
    try:
        _mirror_background_event(
            "[CRON_START]",
            "cron",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "running": True}

def stop() -> Dict[str, Any]:
    with _LOCK:
        _STATE["running"] = False
    _log_audit("Stopped")
    try:
        _mirror_background_event(
            "[CRON_STOP]",
            "cron",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, "running": False}

def add_task(name: str, schedule: Dict[str, Any], action: str, params: Dict[str, Any] = {}, enabled: bool = True) -> Dict[str, Any]:
    from modules.auth.rbac import has_any_role  # type: ignore
    if not has_any_role(["admin"]): return {"ok": False, "error": "rbac_forbidden"}
    j = _load_db()
    t = {"name": name, "schedule": schedule, "action": action, "params": params, "enabled": enabled, "next_ts": _calc_next(schedule), "ts": int(time.time())}
    j["tasks"][name] = t
    _save(j)
    _log_audit(f"Added {name}")
    return {"ok": True, "task": t}

def run_now(name: str) -> Dict[str, Any]:
    from modules.auth.rbac import has_any_role  # type: ignore
    if not has_any_role(["operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    j = _load_db()
    t = j["tasks"].get(name)
    if not t: return {"ok": False, "error": "not_found"}
    if CRON_AB == "B": rep = {"ok": True, "dry_run": True}
    else: rep = _run_action(t["action"], t.get("params", {}))
    t["last_ts"] = int(time.time())
    t["last_out"] = rep
    _save(j)
    _passport(f"cron_run_now_{name}", {"rep": rep})
    _log_audit(f"Ran now {name}: {rep}")
    try:
        _mirror_background_event(
            f"[CRON_RUN_NOW] name={name} ok={int(rep.get('ok'))}",
            "cron",
            "run_now",
        )
    except Exception:
        pass
    return {"ok": rep["ok"], "result": rep}

def list_jobs() -> Dict[str, Any]:
    return {"ok": True, "jobs": _load(), "ab": CRON_AB}


def status() -> Dict[str, Any]:
    jobs = _load()
    return {
        "ok": True,
        "running": bool(_STATE.get("running")),
        "last_tick": int(_STATE.get("last_tick") or 0),
        "jobs_count": int(len(jobs)),
        "ab": CRON_AB,
        "enabled": bool(ENABLE),
    }

@bp_cron.route("/cron/status", methods=["GET"])
def cron_status():
    return jsonify(status())

@bp_cron.route("/cron/add", methods=["POST"])
def cron_add():
    d = request.get_json() or {}
    return jsonify(add_task(d.get("name"), d.get("schedule", {}), d.get("action"), d.get("params", {})))

@bp_cron.route("/cron/run_now/<name>", methods=["POST"])
def cron_run_now(name):
    return jsonify(run_now(name))

@bp_cron.route("/cron/list", methods=["GET"])
def cron_list():
    return jsonify(list_jobs())

@bp_cron.route("/cron/start", methods=["POST"])
def cron_start():
    return jsonify(start())

@bp_cron.route("/cron/stop", methods=["POST"])
def cron_stop():
    return jsonify(stop())

@bp_cron.route("/cron/audit", methods=["GET"])
def cron_audit():
    from modules.auth.rbac import has_any_role  # type: ignore
    if not has_any_role(["admin"]): return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()[-50:]
        return jsonify({"ok": True, "audit": lines})
    except Exception:
        return jsonify({"ok": False, "error": "audit_read_failed"})

def register(app):
    app.register_blueprint(bp_cron)
    if AUTOSTART:
        start()
    return app





