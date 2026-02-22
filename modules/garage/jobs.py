# -*- coding: utf-8 -*-
"""
modules/garage/jobs.py — obedinennyy sborschik/khranilische vakansiy: scan iz RSS/HTTP, import/list/score (token+semantic), s ledger/P2P/scheduler integratsiey.

Mosty:
- Yavnyy: (Internet/Fayly ↔ Proektnaya voronka/Garazh) sbor/import vakansiy, skoring po skills, khranenie v JSON.
- Skrytyy #1: (Memory/Volya ↔ Profile/Puls) profileizatsiya s teplymi notkami, planirovka v Volition.
- Skrytyy #2: (Stoimost ↔ Byudzhet) ledger-spend za score/scan.
- Skrytyy #3: (P2P/Raspredelennost ↔ Integratsiya) sync vakansiy po P2P dlya agentov.

Zemnoy abzats:
Eto ne prosto doska, a umnyy seyf Ester: probezhit po lentam, importiruet svezhie, otsenit po skillam (dazhe semanticheski), sinkhroniziruet po P2P i shepnet v profile "Ester, novye vozmozhnosti — shag k tvoim planam v seti agentov!".

# c=a+b
"""
from __future__ import annotations
import difflib, hashlib, json, os, re, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("GARAGE_ROOT", "data/garage")
AB = (os.getenv("GARAGE_AB", "A") or "A").upper()
SKILLS = [x.strip().lower() for x in (os.getenv("GARAGE_SKILLS", "python,flask,ai,ml,video,tts,rag") or "").split(",") if x.strip()]
CFG = os.getenv("GARAGE_JOBS_CFG", "data/garage/jobsources.json")
STATE = os.getenv("GARAGE_STATE", "data/garage/jobs_state.json")
LOG_PATH = os.getenv("GARAGE_LOG", "data/garage/jobs_log.jsonl")
P2P_SYNC = (os.getenv("GARAGE_P2P_SYNC", "false").lower() == "true")
LLM_SCORE = (os.getenv("GARAGE_LLM_SCORE", "false").lower() == "true")
MIN_SCORE = float(os.getenv("GARAGE_MIN_SCORE", "50"))

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.isfile(os.path.join(ROOT, "jobs.json")):
        json.dump({"jobs": []}, open(os.path.join(ROOT, "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not os.path.isfile(CFG):
        json.dump({"rss": [], "http": []}, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.isfile(LOG_PATH): open(LOG_PATH, "w", encoding="utf-8").close()
    if not os.path.isfile(STATE): json.dump({"last_scan": 0}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load_jobs() -> Dict[str, Any]:
    _ensure()
    j = json.load(open(os.path.join(ROOT, "jobs.json"), "r", encoding="utf-8"))
    # P2P-sync: merge from peers
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_pull  # type: ignore
            remote = p2p_pull("garage_jobs") or {"jobs": []}
            existing_ids = {x["id"] for x in j["jobs"]}
            for rj in remote["jobs"]:
                if rj["id"] not in existing_ids or rj.get("ts", 0) > [x["ts"] for x in j["jobs"] if x["id"] == rj["id"]][0]:
                    j["jobs"] = [x for x in j["jobs"] if x["id"] != rj["id"]] + [rj]
            _save_jobs(j)
        except Exception:
            _append_log({"ts": int(time.time()), "error": "p2p_pull_failed"})
    return j

def _save_jobs(j: Dict[str, Any]):
    json.dump(j, open(os.path.join(ROOT, "jobs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # P2P-push: sync new/updated
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_push  # type: ignore
            p2p_push("garage_jobs", j)
        except Exception:
            pass

def _append_log(rec: Dict[str, Any]):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note + " — Ester, vakansii obnovleny, tvoi plany ozhivayut v seti agentov!", meta, source="garage://jobs")
    except Exception:
        _append_log({"ts": int(time.time()), "passport_failed": note})

def _ledger_spend(cost: float, sink: str):
    try:
        from modules.economy.ledger import spend  # type: ignore
        spend("ester", cost, sink)
    except Exception:
        pass

def _check_rbac(required: List[str]) -> bool:
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(required)
    except Exception:
        return True

def _load_url(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "EsterGarage/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

def scan() -> Dict[str, Any]:
    _ensure()
    cfg = json.load(open(CFG, "r", encoding="utf-8"))
    out = []
    # RSS
    for u in cfg.get("rss", []):
        try:
            xml = _load_url(u)
            root = ET.fromstring(xml)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()
                out.append({"title": title, "link": link, "summary": desc, "source": u})
        except Exception:
            _append_log({"ts": int(time.time()), "scan_rss_failed": u})
    # HTTP (grab title)
    for u in cfg.get("http", []):
        try:
            html = _load_url(u)
            t1 = html.lower().find("<title>")
            t2 = html.lower().find("</title>")
            title = html[t1+7:t2].strip() if (t1 != -1 and t2 != -1) else u
            out.append({"title": title, "link": u, "summary": "", "source": u})
        except Exception:
            _append_log({"ts": int(time.time()), "scan_http_failed": u})
    _append_log({"ts": int(time.time()), "scan": {"items": len(out)}})
    _passport("Jobs scan completed", {"count": len(out)})
    return {"ok": True, "items": out}

def job_import(job: Dict[str, Any]) -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "GARAGE_AB=B (dry_run)"}
    if not _check_rbac(["operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    j = _load_jobs()
    # Normalize
    rec = {
        "id": str(job.get("id") or hashlib.md5((job.get("title", "") + job.get("link", "")).encode()).hexdigest()),
        "title": str(job.get("title", "")).strip(),
        "body": str(job.get("body", "") or job.get("summary", "")).strip(),
        "budget": float(job.get("budget", 0) or 0),
        "currency": str(job.get("currency", "")).upper(),
        "tags": list(job.get("tags") or []),
        "source": str(job.get("source", "")),
        "link": str(job.get("link", "")),
        "ts": int(time.time())
    }
    # Upsert by id
    jobs = j.get("jobs", [])
    for i, x in enumerate(jobs):
        if x.get("id") == rec["id"]:
            jobs[i] = rec
            break
    else:
        jobs.append(rec)
    j["jobs"] = jobs
    _save_jobs(j)
    _passport("Job imported", {"id": rec["id"], "title": rec["title"]})
    _append_log({"ts": int(time.time()), "import": rec})
    return {"ok": True, "job": rec}

def scan_import() -> Dict[str, Any]:
    s = scan()
    imported = []
    j = _load_jobs()
    existing_hashes = {hashlib.md5((x["title"] + x.get("link", "")).encode()).hexdigest() for x in j["jobs"]}
    for item in s["items"]:
        h = hashlib.md5((item["title"] + item.get("link", "")).encode()).hexdigest()
        if h not in existing_hashes:
            imp = job_import(item)
            if imp["ok"]: imported.append(imp["job"])
    if imported: _ledger_spend(0.01 * len(imported), "garage_scan_import")
    return {"ok": True, "imported": len(imported), "items": imported}

def job_list(min_score: float = MIN_SCORE) -> Dict[str, Any]:
    j = _load_jobs()
    items = j.get("jobs", [])
    if min_score > 0:
        filtered = []
        for item in items:
            sc = job_score(item["id"])
            if sc["ok"] and sc["score"] >= min_score:
                item["score"] = sc["score"]
                filtered.append(item)
        items = filtered
    return {"ok": True, "items": items}

def _tokenize(s: str) -> List[str]:
    return re.findall(r"[A-Za-z\u0400-\u04FF0-9]{2,}", (s or "").lower())

def _token_score(text_tokens: List[str]) -> Dict[str, Any]:
    hits = [s for s in SKILLS if s in text_tokens]
    score = round((len(hits) / max(1, len(SKILLS))) * 100, 1)
    return {"score": score, "hits": hits}

def _semantic_lite_score(text_tokens: List[str]) -> Dict[str, Any]:
    text_set = set(text_tokens)
    sem_hits: List[str] = []
    for skill in SKILLS:
        if skill in text_set:
            sem_hits.append(skill)
            continue
        best = 0.0
        for tok in text_set:
            ratio = difflib.SequenceMatcher(a=skill, b=tok).ratio()
            if ratio > best:
                best = ratio
        if best >= 0.82:
            sem_hits.append(skill)
    score = round((len(set(sem_hits)) / max(1, len(SKILLS))) * 100, 1)
    return {"score": score, "hits": sorted(set(sem_hits))}

def job_score(jid: str) -> Dict[str, Any]:
    if not _check_rbac(["viewer", "operator", "admin"]): return {"ok": False, "error": "rbac_forbidden"}
    j = _load_jobs()
    job = next((x for x in j["jobs"] if x["id"] == jid), None)
    if not job: return {"ok": False, "error": "not_found"}
    text = " ".join([job["title"], job["body"], " ".join(job["tags"])])
    tokens = _tokenize(text)
    base = _token_score(tokens)
    if LLM_SCORE:
        try:
            semantic = _semantic_lite_score(tokens)
            score = round((float(base["score"]) * 0.5) + (float(semantic["score"]) * 0.5), 1)
            hits = sorted(set(base["hits"]) | set(semantic["hits"]))
        except Exception:
            score = float(base["score"])
            hits = list(base["hits"])
    else:
        score = float(base["score"])
        hits = list(base["hits"])
    rep = {"ok": True, "id": jid, "score": score, "hits": hits}
    _passport("Job scored", rep)
    _append_log({"ts": int(time.time()), "score": rep})
    _ledger_spend(0.005, "garage_job_score")
    return rep

def export_csv() -> Dict[str, Any]:
    items = job_list(0)["items"]
    csv_path = os.path.join(ROOT, f"jobs_export_{int(time.time())}.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("id,title,budget,currency,score,link\n")
        for item in items:
            sc = job_score(item["id"])["score"]
            f.write(f"{item['id']},{item['title'].replace(',', '')},{item['budget']},{item['currency']},{sc},{item.get('link', '')}\n")
    _passport("Jobs exported to CSV", {"path": csv_path})
    return {"ok": True, "path": csv_path}

# Dlya scheduler: custom action
def scan_import_scheduler(params: Dict[str, Any]) -> Dict[str, Any]:
    return scan_import()

def register(app):
    from flask import Blueprint, request, jsonify
    bp_garage = Blueprint("garage_jobs", __name__)
    @bp_garage.route("/garage/jobs/scan", methods=["POST"])
    def jobs_scan():
        if not _check_rbac(["operator", "admin"]): return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
        return jsonify(scan())
    @bp_garage.route("/garage/jobs/import", methods=["POST"])
    def jobs_import():
        return jsonify(job_import(request.get_json() or {}))
    @bp_garage.route("/garage/jobs/list", methods=["GET"])
    def jobs_list():
        min_sc = float(request.args.get("min_score", MIN_SCORE))
        return jsonify(job_list(min_sc))
    @bp_garage.route("/garage/jobs/score/<jid>", methods=["GET"])
    def jobs_score(jid):
        return jsonify(job_score(jid))
    @bp_garage.route("/garage/jobs/export_csv", methods=["GET"])
    def jobs_export():
        return jsonify(export_csv())
    app.register_blueprint(bp_garage)
    # Scheduler add
    try:
        from modules.cron.scheduler import add_task  # type: ignore
        add_task("garage_jobs_scan_import", {"cron": "@daily"}, "garage.jobs.scan_import_scheduler", {})
    except Exception:
        pass
    return app
