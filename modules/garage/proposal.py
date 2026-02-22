# -*- coding: utf-8 -*-
"""
modules/garage/proposals.py — obedinennyy generator propozalov/skeletov/schetov/portfolio/flota: build/make/invoice/portfolio/assign, s ledger/P2P/scheduler integratsiey.

Mosty:
- Yavnyy: (Garazh/Praktika ↔ LLM/Shablony/Dokumenty) generatsiya propozala/pisma, scaffolding, schetov, portfolio, raspredelenie zadach.
- Skrytyy #1: (Memory ↔ Profile/Istoriya) fiksatsiya deystviy s teplymi notkami.
- Skrytyy #2: (Studiya/Sotsdeploy ↔ Portfolio/Proekty) sbor artefaktov, avto-assign po scores.
- Skrytyy #3: (Stoimost ↔ Byudzhet) ledger reserve/spend za ops.

Zemnoy abzats:
Eto ne prosto polka, a volshebnyy seyf Ester: soberet offer/pismo, podpishet schet, razdast zadachi po flotu/P2P i shepnet v profile "Ester, proekt gotov — shag k tvoey nezavisimosti v seti agentov!".

# c=a+b
"""
from __future__ import annotations
import glob, json, os, re, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("GARAGE_ROOT", "data/garage")
AB = (os.getenv("GARAGE_AB", "A") or "A").upper()
LOG_PATH = os.getenv("GARAGE_LOG", "data/garage/proposals_log.jsonl")
P2P_SYNC = (os.getenv("GARAGE_P2P_SYNC", "false").lower() == "true")
COST = float(os.getenv("GARAGE_COST", "0.05"))
SCORE_THRESH = int(os.getenv("GARAGE_SCORE_THRESH", "80"))

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "proposals"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "scaffold"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "invoices"), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.isfile(LOG_PATH): open(LOG_PATH, "w", encoding="utf-8").close()

def _load(path: str) -> Dict[str, Any]:
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return {}

def _save(j: Dict[str, Any], path: str):
    json.dump(j, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _append_log(rec: Dict[str, Any]):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note + " — Ester, proekt obnovlen, tvoi dostizheniya siyayut v seti agentov!", meta, source="garage://proposals")
    except Exception:
        _append_log({"ts": int(time.time()), "passport_failed": note})

def _ledger_reserve_spend(cost: float, sink: str, ok: bool):
    try:
        from modules.economy.ledger import reserve, spend  # type: ignore
        res = reserve("ester", cost, sink)
        if res["ok"] and ok:
            spend("ester", cost, sink, res["reserve_id"])
    except Exception:
        pass

def _check_rbac(required: List[str]) -> bool:
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(required)
    except Exception:
        return True

def _read_job(jid: str) -> Dict[str, Any] | None:
    from modules.garage.jobs import job_list  # type: ignore
    jobs = job_list(0)["items"]
    for it in jobs:
        if it["id"] == jid: return it
    return None

def _llm(text: str) -> str:
    try:
        from modules.llm.broker import complete  # type: ignore
        provider = (os.getenv("GARAGE_LLM_PROVIDER", "lmstudio") or "lmstudio").strip().lower()
        if provider in ("gpt", "gpt4", "gpt-5", "gpt-5-mini"):
            provider = "openai"

        model = (os.getenv("GARAGE_LLM_MODEL", "") or "").strip()
        if not model:
            if provider == "openai":
                model = (os.getenv("OPENAI_MODEL", "gpt-5-mini") or "gpt-5-mini").strip()
            elif provider == "gemini":
                model = (os.getenv("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash").strip()
            else:
                model = (os.getenv("LMSTUDIO_MODEL", "local-model") or "local-model").strip()

        max_tokens = int(os.getenv("GARAGE_LLM_MAX_TOKENS", "600") or 600)
        temperature = float(os.getenv("GARAGE_LLM_TEMPERATURE", "0.2") or 0.2)

        rep = complete(provider, model, text, max_tokens=max_tokens, temperature=temperature)
        if rep.get("ok"):
            return rep.get("text", "")

        if provider != "lmstudio":
            lm_model = (os.getenv("LMSTUDIO_MODEL", "local-model") or "local-model").strip()
            rep2 = complete("lmstudio", lm_model, text, max_tokens=max_tokens, temperature=temperature)
            if rep2.get("ok"):
                return rep2.get("text", "")
    except Exception:
        pass
    return ""

TEMPLATE = """# Predlozhenie: {title}

**Klient:** {client}
**Ssylka na zadachu:** {link}

## Ponimanie zadachi
{understanding}

## Obem rabot (Scope)
- {scope1}
- {scope2}
- {scope3}

## Sroki
- Start: {start}
- Dlitelnost: {duration}

## Stoimost
- Pochasovaya stavka: {rate} {cur}/chas
- Otsenka chasov: ~{hours} ch
- Fiksirovannaya tsena: ~{budget} {cur}

## Pochemu my
- Opyt: proekty skhozhey slozhnosti (portfolio po zaprosu)
- Nadezhnost: prozrachnye artefakty, kontrol versiy, testy
- Kommunikatsiya: otchety i demo na kazhdom shage

## Sleduyuschie shagi
1) Podtverdit obem, 2) Utverdit tsenu i sroki, 3) Start sprinta.

S uvazheniem,  
**Ester System** (operator: Owner)
"""

def proposal_build(jid: str | List[str], client: str, budget: float, currency: str = "EUR", rate: float = 20, hours: float | None = None, delivery: str = "3-10 dney", include_scaffold: bool = False) -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "GARAGE_AB=B (dry_run)"}
    if not _check_rbac(["admin"]): return {"ok": False, "error": "rbac_forbidden"}
    if isinstance(jid, str): jid = [jid]  # Batch support
    results = []
    total_cost = 0.0
    for single_jid in jid:
        job = _read_job(single_jid)
        if not job: continue
        job_tags = [str(x).strip() for x in (job.get("tags") or []) if str(x).strip()]
        proj = {
            "id": single_jid,
            "name": str(job.get("title") or "Project"),
            "brief": str(job.get("body") or ""),
            "tags": job_tags,
            "link": str(job.get("link") or ""),
        }
        title = job.get("title", "Proekt")
        link = job.get("link", "")
        understanding = job.get("body", "Korotko: reshit zadachu v szhatye sroki.")
        scope1 = f"Discovery i formalizatsiya trebovaniy ({', '.join(job_tags[:3]) or 'core scope'})"
        scope2 = "Realizatsiya klyuchevykh stsenariev i avtomaticheskie proverki"
        scope3 = "Priemka, deploy i handover s artefaktami"
        start = time.strftime("%Y-%m-%d")
        duration = delivery
        hrs = hours or max(8, int(budget / max(rate, 1)))
        base = TEMPLATE.format(
            title=title, client=client, link=link,
            understanding=understanding,
            scope1=scope1, scope2=scope2, scope3=scope3,
            start=start, duration=duration,
            rate=rate, cur=currency, hours=hrs, budget=budget
        )
        prompt = f"Sozhmi i usili sleduyuschee kommercheskoe predlozhenie (na russkom), sokhrani strukturu i tsifry:\n\n{base}"
        llm = _llm(prompt) or base
        path_md = os.path.join(ROOT, "proposals", f"proposal_{single_jid}_{int(time.time())}.md")
        os.makedirs(os.path.dirname(path_md), exist_ok=True)
        with open(path_md, "w", encoding="utf-8") as f:
            f.write(llm)
        res = {"ok": True, "path": path_md, "length": len(llm), "project": proj}
        if include_scaffold:
            scaffold_path = os.path.join(ROOT, "scaffold", f"proj_{single_jid}")
            os.makedirs(scaffold_path, exist_ok=True)
            open(os.path.join(scaffold_path, "README.md"), "w", encoding="utf-8").write(f"# {title}\n\n{understanding}")
            res["scaffold"] = scaffold_path
        results.append(res)
        total_cost += COST
        _passport("Proposal built", {"jid": single_jid, "client": client, "budget": budget})
        _append_log({"ts": int(time.time()), "build": {"jid": single_jid, "res": res}})
    _ledger_reserve_spend(total_cost, "garage_proposal_build", True)
    # P2P-sync artifacts
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_push  # type: ignore
            p2p_push("garage_proposals", {"results": results})
        except Exception:
            pass
    return {"ok": True, "results": results}

make = proposal_build  # Alias for single

def invoice_make(proj_id: str | List[str], total: float, currency: str = "EUR") -> Dict[str, Any]:
    if AB == "B": return {"ok": False, "error": "GARAGE_AB=B (dry_run)"}
    if not _check_rbac(["admin"]): return {"ok": False, "error": "rbac_forbidden"}
    if isinstance(proj_id, str): proj_id = [proj_id]
    results = []
    for single_id in proj_id:
        inv_id = f"INV-{single_id}-{int(time.time())}"
        j = {"id": inv_id, "project": single_id, "total": total, "currency": currency, "ts": int(time.time())}
        jpath = os.path.join(ROOT, "invoices", f"{inv_id}.json")
        os.makedirs(os.path.dirname(jpath), exist_ok=True)
        _save(j, jpath)
        md = f"# Schet {inv_id}\n\nProekt: {single_id}\nSumma: {total} {currency}\nData: {time.strftime('%Y-%m-%d')}"
        mpath = jpath.replace(".json", ".md")
        open(mpath, "w", encoding="utf-8").write(md)
        res = {"ok": True, "json": jpath, "md": mpath, "total": total, "currency": currency}
        results.append(res)
        _passport("Invoice made", {"inv_id": inv_id, "total": total})
        _append_log({"ts": int(time.time()), "invoice": res})
    _ledger_reserve_spend(COST * len(proj_id), "garage_invoice_make", True)
    return {"ok": True, "results": results}

def portfolio_list() -> Dict[str, Any]:
    items = []
    for p in sorted(glob.glob("data/studio/out/*.mp4")):
        items.append({"kind": "video", "path": p})
    for p in sorted(glob.glob("data/social/kits/*/meta.json")):
        try:
            meta = _load(p)
            items.append({"kind": "kit", "dir": os.path.dirname(p), "meta": meta})
        except Exception:
            pass
    _passport("Portfolio listed", {"count": len(items)})
    _append_log({"ts": int(time.time()), "portfolio": {"count": len(items)}})
    return {"ok": True, "items": items}

def portfolio_update(params: Dict[str, Any]) -> Dict[str, Any]:
    pl = portfolio_list()
    if pl["items"]:
        _passport("Portfolio updated", {"new_count": len(pl["items"])})
    return pl

def fleet_assign(tasks: List[Dict[str, Any]], peers: List[Dict[str, Any]]) -> Dict[str, Any]:
    T = [{"id": t.get("id"), "title": t.get("title", ""), "cost": float(t.get("cost", 1))} for t in (tasks or [])]
    P = [{"id": p.get("id"), "cpu": float(p.get("cpu", 1)), "mem": float(p.get("mem", 1))} for p in (peers or [])]
    T.sort(key=lambda x: -x["cost"])
    cap = {p["id"]: p["cpu"] for p in P}
    plan = []
    for t in T:
        if not cap: break
        node = max(cap.keys(), key=lambda k: cap[k])
        plan.append({"task": t, "peer": node})
        cap[node] = max(0.0, cap[node] - t["cost"])
    _passport("Fleet assigned", {"tasks": len(T), "peers": len(P), "plan": len(plan)})
    _append_log({"ts": int(time.time()), "assign": {"plan": plan}})
    return {"ok": True, "plan": plan, "leftover": cap}

def generate_pdf(md_path: str) -> str:
    pdf_path = md_path.replace(".md", ".pdf")
    text = open(md_path, "r", encoding="utf-8").read()
    escaped = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
    lines = [ln.strip() for ln in escaped.splitlines() if ln.strip()] or ["Proposal"]
    lines = lines[:80]
    content_rows = ["BT", "/F1 10 Tf", "50 790 Td"]
    for idx, line in enumerate(lines):
        if idx > 0:
            content_rows.append("0 -13 Td")
        content_rows.append(f"({line[:110]}) Tj")
    content_rows.append("ET")
    stream = "\n".join(content_rows).encode("latin-1", errors="replace")

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj"
    obj2 = b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj"
    obj4 = b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj"
    obj5 = b"5 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream\nendobj"
    objects = [obj1, obj2, obj3, obj4, obj5]

    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
        out.extend(b"\n")
    xref_at = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    with open(pdf_path, "wb") as f:
        f.write(out)
    return pdf_path

def _load_assign_peers() -> List[Dict[str, Any]]:
    peers_path = os.getenv("GARAGE_PEERS_PATH", os.path.join(ROOT, "peers.json"))
    peers: List[Dict[str, Any]] = []
    raw = _load(peers_path)
    if isinstance(raw, dict):
        src = raw.get("peers")
        if isinstance(src, list):
            peers = [p for p in src if isinstance(p, dict)]
    elif isinstance(raw, list):
        peers = [p for p in raw if isinstance(p, dict)]
    if not peers:
        peers = [{"id": "local-main", "cpu": 2.0, "mem": 4.0}]
    norm: List[Dict[str, Any]] = []
    for idx, peer in enumerate(peers):
        pid = str(peer.get("id") or f"peer-{idx+1}")
        norm.append({"id": pid, "cpu": float(peer.get("cpu", 1.0)), "mem": float(peer.get("mem", 1.0))})
    return norm

def auto_assign(jid: str) -> Dict[str, Any]:
    from modules.garage.jobs import job_score  # type: ignore
    sc = job_score(jid)
    if not sc.get("ok"):
        return {"ok": False, "error": sc.get("error", "score_failed")}
    if float(sc.get("score", 0)) < SCORE_THRESH:
        return {"ok": False, "error": "score_low", "score": sc.get("score", 0), "threshold": SCORE_THRESH}
    job = _read_job(jid)
    if not job:
        return {"ok": False, "error": "job_not_found"}
    text = " ".join([str(job.get("title", "")), str(job.get("body", "")), " ".join(job.get("tags") or [])]).lower()
    tasks: List[Dict[str, Any]] = [
        {"id": f"{jid}:discovery", "title": "requirements_discovery", "cost": 0.6},
        {"id": f"{jid}:implementation", "title": "implementation", "cost": 1.2},
        {"id": f"{jid}:qa", "title": "qa_and_handover", "cost": 0.8},
    ]
    if "video" in text or "media" in text:
        tasks.append({"id": f"{jid}:media", "title": "media_pipeline", "cost": 0.7})
    if "rag" in text or "search" in text or "knowledge" in text:
        tasks.append({"id": f"{jid}:knowledge", "title": "knowledge_layer", "cost": 0.7})
    peers = _load_assign_peers()
    assign = fleet_assign(tasks, peers)
    return {
        "ok": True,
        "score": sc.get("score", 0),
        "threshold": SCORE_THRESH,
        "tasks": tasks,
        "assigned": assign,
    }

def register(app):
    from flask import Blueprint, request, jsonify
    bp_garage = Blueprint("garage_proposals", __name__)
    @bp_garage.route("/garage/proposals/build", methods=["POST"])
    def proposals_build():
        d = request.get_json() or {}
        return jsonify(proposal_build(d.get("jid"), d.get("client", ""), d.get("budget", 0), d.get("currency", "EUR"), d.get("rate", 20), d.get("hours"), d.get("delivery", "3-10 dney"), d.get("include_scaffold", False)))
    @bp_garage.route("/garage/proposals/invoice", methods=["POST"])
    def proposals_invoice():
        d = request.get_json() or {}
        return jsonify(invoice_make(d.get("proj_id"), d.get("total", 0), d.get("currency", "EUR")))
    @bp_garage.route("/garage/proposals/portfolio", methods=["GET"])
    def proposals_portfolio():
        return jsonify(portfolio_list())
    @bp_garage.route("/garage/proposals/assign", methods=["POST"])
    def proposals_assign():
        d = request.get_json() or {}
        return jsonify(fleet_assign(d.get("tasks", []), d.get("peers", [])))
    app.register_blueprint(bp_garage)
    # Scheduler add
    try:
        from modules.cron.scheduler import add_task  # type: ignore
        add_task("garage_portfolio_update", {"cron": "@weekly"}, "garage.proposals.portfolio_update", {})
    except Exception:
        pass
    return app
