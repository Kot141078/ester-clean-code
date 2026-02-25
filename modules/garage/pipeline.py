# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules/garage/pipeline.py - yadro konveyera Garage/Workbench
(poisk → scoring → generatsiya → autrich → billing → otchet)

Most (yavnyy):
  • (FS/lokal ↔ Web/backend) — konveyer pishet artefakty v ponyatnuyu ierarkhiyu (workbench/, outbox/, billing/) i daet API.

Skrytye mosty:
  • (Kibernetika ↔ Inzheneriya protsessov) - A/B-sloty i avto-otkat: riskovannye operatsii idut v slote B s bystrym rollback.
  • (Ekonomika ↔ Infoteoriya) - edinyy format brifa snizhaet “trenie” mezhdu istochnikami (JSON/JSONL/katalogi).

Zemnoy abzats:
Kak tsekh s konveyerom: magazin zagotovok (inbox istochniki), kalibr (skoring/resursy), frezer (generatsiya proekta),
konveyernaya podacha (autrich), kassa i nakladnye (invoysy/otchety). All logiruetsya v zhurnaly JSONL.

ENV (optional):
  • ESTER_ROOT - koren proekta (by umolchaniyu avtoopredelenie)
  • GARAGE_AB_MODE=A|B - A (polnyy prokhod) / B (schadyaschiy: bez vneshnikh otpravok; tolko outbox)
  • OUTREACH_WEBHOOK_URL — esli zadan, autrich ukhodit HTTP POST'om (dopolnitelno k outbox)
  • PAY_NAME, PAY_IBAN, PAY_BIC, PAY_ADDR — rekvizity dlya invoysa, esli net data/pay/prefs.json

# c=a+b"""
import dataclasses
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# -------------------------- vspomogatelnye utility --------------------------

def _project_root() -> Path:
    # 1) ENV
    e = os.getenv("ESTER_ROOT")
    if e:
        p = Path(e).resolve()
        if p.exists():
            return p
    # 2) ryadom s app.py
    here = Path(__file__).resolve()
    for up in [here] + list(here.parents):
        if (up / "app.py").exists():
            return up
    # 3) falbatsk - current process directory
    return Path.cwd().resolve()


ROOT = _project_root()
DATA = ROOT / "data"
GARAGE_DATA = DATA / "garage"
PAY_DATA = DATA / "pay"
WORKBENCH = ROOT / "workbench"
OUTBOX = ROOT / "outbox" / "garage"
BILLING = ROOT / "billing"
LOGS = ROOT / "logs" / "garage"

for d in (WORKBENCH, OUTBOX, BILLING, LOGS):
    d.mkdir(parents=True, exist_ok=True)


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "job"


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# -------------------------- model brifa --------------------------

@dataclasses.dataclass
class Job:
    id: str
    title: str
    description: str
    skills: List[str]
    budget: float
    currency: str
    deadline: Optional[str]  # ISO
    source: str
    meta: Dict[str, Any]


def _normalize_job(raw: Dict[str, Any], source: str) -> Job:
    title = str(raw.get("title") or raw.get("name") or "Untitled")
    desc = str(raw.get("description") or raw.get("desc") or "")
    skills = raw.get("skills") or raw.get("tags") or []
    if isinstance(skills, str):
        skills = re.split(r"[,; ]+", skills)
    budget = float(raw.get("budget", 0) or raw.get("price", 0) or 0)
    currency = str(raw.get("currency") or "USD")
    deadline = raw.get("deadline") or raw.get("due") or None
    jid = raw.get("id") or _slug(f"{title}-{_sha256_hex((title+desc).encode('utf-8'))[:6]}")
    return Job(
        id=str(jid),
        title=title.strip(),
        description=desc.strip(),
        skills=[str(s).strip().lower() for s in skills if str(s).strip()],
        budget=budget,
        currency=currency,
        deadline=str(deadline) if deadline else None,
        source=source,
        meta={k: v for k, v in raw.items() if k not in {"id", "title", "name", "description", "desc", "skills", "tags", "budget", "price", "currency", "deadline", "due"}},
    )


# -------------------------- skan istochnikov --------------------------

def _scan_jobsources() -> List[Dict[str, Any]]:
    cfg = GARAGE_DATA / "jobsources.json"
    if not cfg.exists():
        return []
    data = _read_json(cfg, default=[])
    return data if isinstance(data, list) else []


def _iter_jobs_from_source(src: Dict[str, Any]) -> Iterable[Job]:
    stype = (src.get("type") or "").lower()
    if stype == "jsonl":
        p = Path(src.get("path") or "")
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    yield _normalize_job(raw, f"file:{p.name}")
                except Exception:
                    continue
    elif stype == "json":
        p = Path(src.get("path") or "")
        if p.exists():
            raw = _read_json(p, default=[])
            if isinstance(raw, list):
                for r in raw:
                    yield _normalize_job(r, f"file:{p.name}")
            elif isinstance(raw, dict):
                yield _normalize_job(raw, f"file:{p.name}")
    elif stype == "folder":
        # Files *.eb.zsion as single briefs
        p = Path(src.get("path") or "")
        if p.exists():
            for f in p.glob("*.job.json"):
                try:
                    raw = _read_json(f, default={})
                    if raw:
                        yield _normalize_job(raw, f"folder:{p.name}")
                except Exception:
                    continue
    # other types can be added without breaking the contract


def scan_jobs() -> List[Dict[str, Any]]:
    jobs: List[Job] = []
    for src in _scan_jobsources():
        jobs.extend(list(_iter_jobs_from_source(src)))
    # Vozvraschaem normalizovannye slovari
    return [dataclasses.asdict(j) for j in jobs]


# -------------------------- skoring/resursy --------------------------

def _estimate_resources(job: Job) -> Dict[str, Any]:
    cores = os.cpu_count() or 2
    # rough model ETA ~ 1 / (skrt(budget)+1) + penalty for the term
    import math
    eta_hours = max(1.0, 40.0 / (math.sqrt(max(job.budget, 1.0)) + 1.0))
    if job.deadline:
        try:
            # the closer the deadline, the higher the priority (lower ETA)
            eta_hours *= 0.8
        except Exception:
            pass
    need = {"cpu": min(cores, 8), "ram_gb": 4, "gpu": 0}
    score = min(1.0, (job.budget / 1000.0) + (len(job.skills) * 0.05))
    return {"score": round(score, 3), "eta_hours": round(eta_hours, 1), "need": need, "node_hint": "local"}


# -------------------------- generatsiya proekta --------------------------

def _project_dir(job: Job) -> Path:
    return WORKBENCH / _slug(job.id)


def _write_text(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def generate_project(job_or_id: Any) -> Dict[str, Any]:
    job = _resolve_job(job_or_id)
    if not job:
        return {"ok": False, "error": "job_not_found"}

    r = _estimate_resources(job)
    pd = _project_dir(job)
    if pd.exists():
        shutil.rmtree(pd)
    pd.mkdir(parents=True, exist_ok=True)

    readme = (
        f"# {job.title}\n\n"
        f"Istochnik: {job.source}\n\n"
        f"## Opisanie\n{job.description}\n\n"
        f"## Navyki\n- " + "\n- ".join(job.skills) + f"\n\n## Resursy\n{_json_dumps(r)}\n"
    )
    _write_text(pd / "README.md", readme)

    # Prosteyshiy lending
    index_html = f"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>{job.title}</title><body><h1>{job.title}</h1><p>{job.description}</p>
<p><b>Navyki:</b> {", ".join(job.skills)}</p>
<p><i>Istochnik:</i> {job.source}</p>
</body></html>"""
    _write_text(pd / "site" / "index.html", index_html)

    # Draft proposal (pitch)
    pitch = f"""### Predlozhenie po zadache: {job.title}

Zdravstvuyte! Kratko po podkhodu:

1) Bystryy prototip i soglasovanie kriteriev priemki.
2) Prozrachnyy plan: repozitoriy, doska zadach, otchetnost po vekham.
3) Soblyudenie dedlayna i byudzhetnoy ramki.

**Otsenka:** ~{r['eta_hours']} ch.  |  Byudzhet: {job.budget} {job.currency}

S nailuchshimi,  
Ester / Garage
"""
    _write_text(pd / "proposal.md", pitch)

    # Logirovanie
    _append_jsonl(LOGS / "pipeline.jsonl", {"ts": _now_iso(), "event": "generate", "job_id": job.id, "project_dir": str(pd)})
    return {"ok": True, "job": dataclasses.asdict(job), "resources": r, "project_dir": str(pd)}


# -------------------------- autrich --------------------------

def _outbox_path(job: Job) -> Path:
    return OUTBOX / f"{_slug(job.id)}_pitch.txt"


def _load_pay_prefs() -> Dict[str, Any]:
    p = PAY_DATA / "prefs.json"
    if p.exists():
        prefs = _read_json(p, default={})
    else:
        prefs = {}
    # dopolnim iz ENV pri neobkhodimosti
    prefs.setdefault("name", os.getenv("PAY_NAME", "Ester"))
    prefs.setdefault("iban", os.getenv("PAY_IBAN", ""))
    prefs.setdefault("bic", os.getenv("PAY_BIC", ""))
    prefs.setdefault("addr", os.getenv("PAY_ADDR", ""))
    return prefs


def _outreach_payload(job: Job, project_dir: Path) -> Dict[str, Any]:
    prefs = _load_pay_prefs()
    url_preview = f"file://{project_dir.as_posix()}/site/index.html"
    return {
        "title": job.title,
        "preview": url_preview,
        "budget": {"value": job.budget, "currency": job.currency},
        "skills": job.skills,
        "pay_prefs": prefs,
    }


def send_outreach(job_or_id: Any) -> Dict[str, Any]:
    job = _resolve_job(job_or_id)
    if not job:
        return {"ok": False, "error": "job_not_found"}
    pd = _project_dir(job)
    if not pd.exists():
        gen = generate_project(job)
        if not gen.get("ok"):
            return gen

    payload = _outreach_payload(job, pd)
    pitch_text = f"{job.title}\n\n{_json_dumps(payload)}\n"
    pitch_file = _outbox_path(job)
    _write_text(pitch_file, pitch_text)

    # Webhook (in addition to boxbox), if specified
    hook = os.getenv("OUTREACH_WEBHOOK_URL", "").strip()
    hook_res: Optional[Tuple[int, str]] = None
    if hook:
        try:
            r = requests.post(hook, json={"type": "garage_pitch", "job_id": job.id, "payload": payload}, timeout=10)
            hook_res = (r.status_code, (r.text or "")[:200])
        except Exception as e:
            hook_res = (-1, str(e))

    _append_jsonl(LOGS / "pipeline.jsonl", {"ts": _now_iso(), "event": "outreach", "job_id": job.id, "pitch_file": str(pitch_file), "hook": hook_res})
    return {"ok": True, "job_id": job.id, "pitch_file": str(pitch_file), "webhook": hook_res}


# -------------------------- billing --------------------------

def _invoice_dir(job: Job) -> Path:
    return BILLING / "invoices" / _slug(job.id)


def _invoice_number(job: Job) -> str:
    return f"INV-{_slug(job.id)}-{datetime.utcnow().strftime('%Y%m%d')}"


def _amount_from_job(job: Job) -> float:
    return float(job.budget or 0.0)


def create_invoice(job_or_id: Any) -> Dict[str, Any]:
    job = _resolve_job(job_or_id)
    if not job:
        return {"ok": False, "error": "job_not_found"}
    inv_dir = _invoice_dir(job)
    inv_dir.mkdir(parents=True, exist_ok=True)
    prefs = _load_pay_prefs()
    num = _invoice_number(job)
    doc = {
        "number": num,
        "date": datetime.utcnow().date().isoformat(),
        "seller": prefs,
        "buyer": {"name": job.meta.get("client", "Client"), "addr": job.meta.get("client_addr", "")},
        "items": [{"title": job.title, "qty": 1, "price": _amount_from_job(job), "currency": job.currency}],
        "total": {"value": _amount_from_job(job), "currency": job.currency},
        "job_id": job.id,
    }
    (inv_dir / "invoice.json").write_text(_json_dumps(doc), encoding="utf-8")
    # ChSV for import into accounting
    csv_lines = ["number,date,title,qty,price,currency,total"]
    csv_lines.append(f"{num},{doc['date']},{job.title.replace(',', ' ')},1,{_amount_from_job(job)},{job.currency},{_amount_from_job(job)}")
    (inv_dir / "invoice.csv").write_text("\n".join(csv_lines), encoding="utf-8")

    _append_jsonl(LOGS / "pipeline.jsonl", {"ts": _now_iso(), "event": "invoice", "job_id": job.id, "invoice": num})
    return {"ok": True, "job_id": job.id, "invoice": num, "dir": str(inv_dir)}


# -------------------------- otchet --------------------------

def daily_report(day_iso: str) -> Dict[str, Any]:
    """Summary of events for the day from logs/garage/pipeline.zsionl"""
    y, m, d = (int(day_iso[0:4]), int(day_iso[5:7]), int(day_iso[8:10]))
    day_prefix = f"{y:04d}-{m:02d}-{d:02d}"
    stats = {"generate": 0, "outreach": 0, "invoice": 0, "errors": 0}
    details: List[Dict[str, Any]] = []

    p = LOGS / "pipeline.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not str(row.get("ts", "")).startswith(day_prefix):
                continue
            ev = row.get("event")
            if ev in stats:
                stats[ev] += 1
            if row.get("error"):
                stats["errors"] += 1
            details.append(row)

    return {"ok": True, "date": day_iso, "summary": stats, "events": details}


# -------------------------- konveyer (A/B + rollback) --------------------------

def _resolve_job(job_or_id: Any) -> Optional[Job]:
    if isinstance(job_or_id, Job):
        return job_or_id
    if isinstance(job_or_id, dict):
        return _normalize_job(job_or_id, source=str(job_or_id.get("source") or "api"))
    if isinstance(job_or_id, str):
        # We are trying to find in the current scan
        for j in scan_jobs():
            if j.get("id") == job_or_id:
                return _normalize_job(j, j.get("source") or "scan")
        # Follbek: sobrat iz artefaktov workbench
        pd = WORKBENCH / _slug(job_or_id)
        if (pd / "README.md").exists():
            # minimal reconstruction (by name)
            return Job(id=_slug(job_or_id), title=job_or_id, description="", skills=[], budget=0.0, currency="USD", deadline=None, source="workbench", meta={})
    return None


def _ab_mode() -> str:
    return (os.getenv("GARAGE_AB_MODE", "A") or "A").strip().upper()


def run_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    """Universal launch:
      - params={"eb": ZZF0Z} or ZZF1ZZ or ZZF2ZZ
    Result: ZFzZZ"""
    # Vybor brifa
    job: Optional[Job] = None
    if "job" in params:
        job = _resolve_job(params["job"])
    elif "job_id" in params:
        job = _resolve_job(str(params["job_id"]))
    elif params.get("auto"):
        pool = [_normalize_job(j, j.get("source") or "scan") for j in scan_jobs()]
        if pool:
            # luchshiy po skoru
            scored = [(j, _estimate_resources(j)["score"]) for j in pool]
            scored.sort(key=lambda x: x[1], reverse=True)
            job = scored[0][0]
    if not job:
        return {"ok": False, "error": "no_job"}

    steps: List[Dict[str, Any]] = []
    rollback = False
    mode = _ab_mode()

    def _step(name: str, fn, *a, **kw) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            res = fn(*a, **kw)
            ok = bool(res.get("ok"))
            return {"name": name, "ok": ok, "ms": round((time.perf_counter() - t0) * 1000.0, 1), "res": res}
        except Exception as e:
            return {"name": name, "ok": False, "ms": round((time.perf_counter() - t0) * 1000.0, 1), "error": str(e)}

    # Step 1: Project generation (always)
    s1 = _step("generate", generate_project, job)
    steps.append(s1)
    if not s1["ok"]:
        _append_jsonl(LOGS / "pipeline.jsonl", {"ts": _now_iso(), "event": "error", "job_id": job.id, "stage": "generate", "error": s1.get("error") or s1["res"].get("error")})
        return {"ok": False, "job_id": job.id, "steps": steps, "rollback": False}

    # Step 2: Outreach
    if mode == "A":
        s2 = _step("outreach", send_outreach, job)
    else:
        # V-slot: only otbox (without webhook) - we will reach the same send_morning, but without ENV MORNING_WEBHOOK_URL
        hook_old = os.environ.get("OUTREACH_WEBHOOK_URL", "")
        try:
            if hook_old:
                os.environ["OUTREACH_WEBHOOK_URL"] = ""
            s2 = _step("outreach", send_outreach, job)
        finally:
            if hook_old:
                os.environ["OUTREACH_WEBHOOK_URL"] = hook_old
    steps.append(s2)

    # Shag 3: invoys
    s3 = _step("invoice", create_invoice, job)
    steps.append(s3)

    ok = bool(s1["ok"] and s2["ok"] and s3["ok"])

    # Auto-rollback when failing in A-slot: remove newly created artifacts
    if (mode == "A") and (not ok):
        try:
            pd = _project_dir(job)
            if pd.exists():
                shutil.rmtree(pd, ignore_errors=True)
            inv = _invoice_dir(job)
            if inv.exists():
                shutil.rmtree(inv, ignore_errors=True)
            rollback = True
        except Exception:
            rollback = False

    _append_jsonl(LOGS / "pipeline.jsonl", {"ts": _now_iso(), "event": "run", "job_id": job.id, "ok": ok, "mode": mode, "rollback": rollback})
    return {"ok": ok, "job_id": job.id, "steps": steps, "rollback": rollback}