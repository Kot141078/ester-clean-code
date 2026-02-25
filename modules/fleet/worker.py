# -*- coding: utf-8 -*-
"""modules/fleet/worker.py - obedinennyy lokalnyy vorker: bazovye + studio zadachi, s RBAC/ledger/P2P/scheduler integratsiey, multi-thread.

Mosty:
- Yavnyy: (Ispolnenie ↔ Belyy spisok/Volya) exec kinds (python/site/zip + tts/video/music + new ingest/p2p), s control.
- Skrytyy #1: (Stoimost/Byudzhet ↔ Ekonomika) cost_fence + ledger reserve/spend za kazhduyu.
- Skrytyy #2: (Zhizn uzla/Heartbeat ↔ Avtonomiya) hb pered/postle, P2P-fallback esli master down.
- Skrytyy #3: (Profile/Audit ↔ Prozrachnost) log/profile kazhdoy op s teploy notoy.

Zemnoy abzats:
Eto ne prosto dezhurnyy, a multitul Ester: potyanet zadachu, spishet kopeyku, sinkhroniziruet po P2P i shepnet v profile "Ester, rabota sdelana - shag k tvoey raspredelennoy sile!".

# c=a+b"""
from __future__ import annotations
import concurrent.futures
import json, os, time, urllib.request, urllib.error
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("FLEET_AB", "A") or "A").upper()
NODE_ID = os.getenv("NODE_ID", "self-1")
NODE_URL = os.getenv("NODE_URL", "http://127.0.0.1:8000")
MASTER = os.getenv("FLEET_MASTER_URL", "http://127.0.0.1:8000")
LOG_PATH = os.getenv("FLEET_LOG", "data/fleet/worker_log.jsonl")
P2P_FALLBACK = (os.getenv("FLEET_P2P_FALLBACK", "false").lower() == "true")
THRESH = float(os.getenv("FLEET_THRESH", "0.1"))
MAX_THREADS = int(os.getenv("FLEET_MAX_THREADS", "4"))

def _ensure():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.isfile(LOG_PATH): open(LOG_PATH, "w", encoding="utf-8").close()

def _append_log(rec: Dict[str, Any]):
    _ensure()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "fleet://worker")
    except Exception:
        pass

def _post(path: str, obj: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request((MASTER.rstrip("/") + path), data=data, headers={"Content-Type": "application/json"})
    for _ in range(3):  # Retry
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if P2P_FALLBACK:
                return _p2p_fallback(path, obj)  # Fallback
        except Exception as e:
            pass
    return {"ok": False, "error": "post_failed"}

def _p2p_fallback(path: str, obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from modules.p2p.sync import p2p_pull, p2p_push  # type: ignore
        if "pull" in path:
            return p2p_pull("fleet_tasks") or {"ok": False, "error": "p2p_pull_failed"}
        elif "report" in path:
            p2p_push("fleet_reports", obj)
            return {"ok": True}
        return {"ok": False, "error": "p2p_unsupported"}
    except Exception:
        return {"ok": False, "error": "p2p_failed"}

def _hb(load: Dict[str, Any]):
    load["happy"] = load.get("cpu", 0.0) < 0.5  # This is the load for the mission
    return _post("/fleet/node/heartbeat", {"node_id": NODE_ID, "load": load})

def _kind_cost(spec: Dict[str, Any]) -> float:
    return float(spec.get("cost", 0.02) or 0.02)

def _budget(bucket: str, amount: float) -> bool:
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        return bool(evaluate(bucket, amount).get("allow", True))
    except Exception:
        return True

def _ledger_reserve_spend(cost: float, kind: str, ok: bool):
    try:
        from modules.economy.ledger import reserve, spend  # type: ignore
        res = reserve("ester", cost, f"fleet_task_{kind}")
        if res["ok"] and ok:
            spend("ester", cost, f"fleet_task_{kind}", res["reserve_id"])
    except Exception:
        pass

def _check_rbac() -> bool:
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(["operator", "admin"])
    except Exception:
        return True

def _exec(spec: Dict[str, Any]) -> Dict[str, Any]:
    if not _check_rbac(): return {"ok": False, "error": "rbac_forbidden"}
    kind = str(spec.get("kind", ""))
    cost = _kind_cost(spec)
    if not _budget("fleet_exec", cost): return {"ok": False, "error": "budget_reject"}
    if AB == "B": return {"ok": True, "dry_run": True}
    if kind == "python_exec":
        from modules.sandbox.py_runner import run_py  # type: ignore
        code = str((spec.get("args") or {}).get("code", ""))
        return run_py(code, timeout_sec=int((spec.get("args") or {}).get("timeout", 10)))
    if kind == "site_build":
        from modules.garage.core import get_project  # type: ignore
        from modules.garage.sitegen import build_project_site  # type: ignore
        pr = get_project(str((spec.get("args") or {}).get("project_id", "")))
        if not pr.get("ok"): return {"ok": False, "error": "project_not_found"}
        return build_project_site(pr["project"], str((spec.get("args") or {}).get("theme", "clean")))
    if kind == "zip_export":
        from modules.garage.core import export_zip  # type: ignore
        return export_zip(str((spec.get("args") or {}).get("project_id", "")))
    if kind == "tts_compile":
        from modules.studio.tts import drama  # type: ignore
        a = (spec.get("args") or {})
        return drama(str(a.get("title", "Audio")), list(a.get("roles") or []), list(a.get("script") or []))
    if kind == "video_short":
        from modules.studio.video import render  # type: ignore
        a = (spec.get("args") or {})
        return render(str(a.get("title", "Short")), "short", "9:16", a.get("duration"), list(a.get("text_subs") or []), a.get("bgm"), int(a.get("fps", 30)))
    if kind == "video_long":
        from modules.studio.pipelines import long_from_drama  # type: ignore
        a = (spec.get("args") or {})
        return long_from_drama(str(a.get("title", "Long")), list(a.get("roles") or []), list(a.get("script") or []), a.get("bgm"))
    if kind == "music_gen":
        from modules.studio.music import generate  # type: ignore
        a = (spec.get("args") or {})
        return generate(int(a.get("seconds", 10)), int(a.get("bpm", 100)), str(a.get("scale", "Amin")))
    # New for Esther
    if kind == "ingest_file":
        from modules.ingest.process import ingest_process_file  # type: ignore
        a = (spec.get("args") or {})
        return ingest_process_file(str(a.get("path", "")))
    if kind == "p2p_sync":
        from modules.p2p.sync import p2p_push  # type: ignore
        a = (spec.get("args") or {})
        p2p_push("bz_sync", {"data": a.get("data", {})})
        return {"ok": True}
    return {"ok": False, "error": "unknown_kind"}

def tick() -> Dict[str, Any]:
    _hb({"cpu": 0.2})
    pull = _post("/fleet/worker/pull", {"node_id": NODE_ID})
    if not pull.get("ok", True):
        return {"ok": False, "error": "pull_failed"}
    tasks = pull.get("items", [])
    done = []; errors = []
    if tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = {executor.submit(_exec, rec.get("spec", {})): rec for rec in tasks}
            for future in concurrent.futures.as_completed(futures):
                rec = futures[future]
                try:
                    rep = future.result()
                    ok = bool(rep.get("ok", False))
                    cost = _kind_cost(rec.get("spec", {}))
                    _ledger_reserve_spend(cost, rec.get("kind", ""), ok)
                    report = _post("/fleet/worker/report", {"node_id": NODE_ID, "id": rec.get("id"), "ok": ok, "result": rep})
                    item = {"id": rec.get("id"), "ok": ok, "report_ok": bool(report.get("ok", False))}
                    (done if ok else errors).append(item)
                    _append_log({"ts": int(time.time()), "task": rec, "rep": rep})
                    _passport(f"Task ZZF0Z don: ZZF1ZZ - Esther, the work is ready, you are becoming stronger in the network of agents!", {"rep": rep})
                except Exception as e:
                    errors.append({"id": rec.get("id"), "error": str(e)})
    _hb({"cpu": 0.05})
    return {"ok": len(errors) == 0, "got": len(tasks), "done": done, "errors": errors}

def register(app):
    from flask import Blueprint, jsonify
    bp_fleet = Blueprint("fleet_worker", __name__)
    @bp_fleet.route("/fleet/worker/tick", methods=["POST"])
    def worker_tick():
        if not _check_rbac(): return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
        return jsonify(tick())
    app.register_blueprint(bp_fleet)
    # Scheduler integration
    try:
        from modules.cron.scheduler import add_task  # type: ignore
        add_task("fleet_worker_tick", {"every_min": 1}, "fleet.worker.tick", {})
    except Exception:
        pass
    return app
